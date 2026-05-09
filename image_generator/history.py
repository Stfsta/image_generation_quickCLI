"""
Conversation history management with atomic writes and session isolation.
对话历史管理模块，支持原子写入和会话隔离。
"""

import json
import tempfile
import os
from pathlib import Path
from datetime import datetime
from typing import Any
from dataclasses import dataclass, asdict
from threading import Lock

from .i18n import text


@dataclass
class Message:
    """Represents a single conversation message.
    表示单个对话消息。"""
    role: str
    content: str
    timestamp: str

    @classmethod
    def now(cls, role: str, content: str) -> "Message":
        return cls(
            role=role,
            content=content,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class HistoryManager:
    """
    Thread-safe conversation history manager with atomic file writes,
    configurable truncation, and session isolation.
    线程安全的对话历史管理器，支持原子文件写入、可配置截断和会话隔离。
    """

    def __init__(self, history_file: Path | str, max_history: int = 10) -> None:
        self._history_path = Path(history_file)
        self._max_history = max(1, max_history)
        self._lock = Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Ensure the history file exists.
        确保历史文件存在。"""
        if not self._history_path.exists():
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write({})

    def _atomic_write(self, data: dict[str, Any]) -> None:
        """Write data atomically using a temporary file and rename.
        使用临时文件和重命名操作实现原子写入。"""
        fd, temp_path = tempfile.mkstemp(
            dir=self._history_path.parent,
            suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self._history_path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _load_all(self) -> dict[str, list[dict[str, str]]]:
        """Load all session data from disk.
        从磁盘加载所有会话数据。"""
        try:
            with open(self._history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _load_session_locked(self, data: dict[str, list[dict[str, str]]], session_id: str) -> list[Message]:
        """Load messages for a session from already-loaded data.
        从已加载的数据中读取指定会话消息（调用方负责加锁）。"""
        raw_messages = data.get(session_id, [])
        messages = [
            Message(msg["role"], msg["content"], msg.get("timestamp", ""))
            for msg in raw_messages
        ]
        return messages[-self._max_history * 2:]

    def _save_session_locked(self, data: dict[str, list[dict[str, str]]], session_id: str, history: list[Message]) -> None:
        """Save a session to already-loaded data and persist atomically.
        将指定会话写入已加载数据并原子持久化（调用方负责加锁）。"""
        data[session_id] = [
            msg.to_dict() for msg in history[-self._max_history * 2:]
        ]
        self._atomic_write(data)

    def load(self, session_id: str = "default") -> list[Message]:
        """
        Load conversation history for a specific session.
        Returns at most max_history * 2 messages (user + assistant pairs).
        加载指定会话的对话历史。
        最多返回 max_history * 2 条消息（用户+助手对）。
        """
        with self._lock:
            data = self._load_all()
            return self._load_session_locked(data, session_id)

    def save(self, session_id: str, history: list[Message]) -> None:
        """
        Save conversation history for a specific session with truncation.
        Uses atomic writes to prevent data corruption.
        保存指定会话的对话历史，带有截断功能。
        使用原子写入防止数据损坏。
        """
        with self._lock:
            data = self._load_all()
            self._save_session_locked(data, session_id, history)

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append a new message to the specified session.
        向指定会话追加一条新消息。"""
        with self._lock:
            data = self._load_all()
            history = self._load_session_locked(data, session_id)
            history.append(Message.now(role, content))
            self._save_session_locked(data, session_id, history)

    def clear(self, session_id: str = "default") -> None:
        """Clear history for a specific session.
        清空指定会话的历史记录。"""
        with self._lock:
            data = self._load_all()
            if session_id in data:
                del data[session_id]
                self._atomic_write(data)

    def build_context_prompt(self, user_input: str, session_id: str = "default", language: str = "en") -> str:
        """
        Build a contextual prompt from session history and current input.
        Previous assistant outputs are summarized to reduce token usage.
        根据会话历史和当前输入构建上下文提示词。
        之前的助手输出会被简化以减少 token 使用。
        """
        history = self.load(session_id)
        if len(history) <= 1:
            return user_input

        context_parts = []
        for msg in history[:-1]:
            content = text(language, "history_generated_placeholder") if msg.role == "assistant" else msg.content
            context_parts.append(f"{msg.role}: {content}")

        context_str = "\n".join(context_parts)
        return (
            f"{text(language, 'history_dialogue_header')}\n"
            f"{context_str}\n\n"
            f"{text(language, 'history_latest_request', request=user_input)}"
        )
