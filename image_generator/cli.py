"""
Command-line interface with enhanced UX and command parsing.
命令行界面，支持增强的用户体验和命令解析。
"""

import sys
from pathlib import Path

from .image_service import ImageGenerationService
from .config import ConfigValidationError


class CLI:
    """
    Interactive command-line interface for the image generation tool.
    Supports commands for history management, configuration reload, and help.
    图像生成工具的交互式命令行界面。
    支持历史管理、配置重新加载和帮助等命令。
    """

    COMMANDS = {
        "exit": ("Exit program / 退出程序", lambda svc, sid, arg: sys.exit(0)),
        "quit": ("Exit program / 退出程序", lambda svc, sid, arg: sys.exit(0)),
        "q": ("Exit program / 退出程序", lambda svc, sid, arg: sys.exit(0)),
        "clear": ("Clear session history / 清空当前会话历史", lambda svc, sid, arg: svc.clear_history(sid)),
        "session": ("Show or switch session ID (usage: session [id]) / 查看或切换会话 ID (用法: session [id])", None),
        "help": ("Show help / 显示帮助信息", None),
        "ref": ("Set/clear reference image (usage: ref <path/url>|clear) / 设置/清除参考图片 (用法: ref <路径/URL>|clear)", None),
    }

    def __init__(self, service: ImageGenerationService | None = None) -> None:
        self._service = service
        self._session_id = "default"
        self._reference_image = None

    @property
    def service(self) -> ImageGenerationService:
        if self._service is None:
            self._service = ImageGenerationService()
        return self._service

    def _print_banner(self) -> None:
        image_dir = Path(self.service.config.image_dir)
        print("\n" + "=" * 60)
        print("    Suchuang API Image Generator (gpt-image-2) v0.1.1")
        print("    速创API 图像生成工具（gpt-image-2）v0.1.1")
        print("=" * 60)
        print("Usage / 使用说明:")
        print("  - Type a prompt or command / 输入提示词或命令")
        print("  - Continuous input to refine based on history / 连续输入可基于历史对话调整图像")
        print("  - Local PNG refs (<=4MB) use edits API / 本地 PNG 参考图(<=4MB)走 edits 接口")
        print("  - Type 'exit' or 'quit' to exit / 输入 'exit' 或 'quit' 退出程序")
        print("  - Type 'clear' to clear session history / 输入 'clear' 清空当前会话历史")
        print("  - Type 'session' to show current session ID / 输入 'session' 查看当前会话 ID")
        print("  - Type 'session <id>' to switch session / 输入 'session <id>' 切换会话")
        print("  - Type 'help' for available commands / 输入 'help' 显示帮助")
        print(f"  Image directory / 图片保存目录: {image_dir.absolute()}")
        print("-" * 60)
        print(f"Current session / 当前会话: {self._session_id}\n")

    def _print_help(self) -> None:
        print("\nAvailable Commands / 可用命令:")
        for cmd, (desc, _) in self.COMMANDS.items():
            print(f"  {cmd:<10} - {desc}")
        print("  <prompt>   - Generate image / 输入提示词生成图像")
        print()

    def _handle_command(self, user_input: str) -> bool:
        """
        Parse and handle special commands.
        Returns True if the input was a command and was handled.
        解析并处理特殊命令。
        如果输入是命令且已处理，则返回 True。
        """
        parts = user_input.split(maxsplit=1)
        if not parts:
            return False

        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd not in self.COMMANDS:
            return False

        desc, handler = self.COMMANDS[cmd]

        if cmd == "session" and not arg:
            print(f"[Info/信息] Current session ID: {self._session_id} / 当前会话 ID: {self._session_id}")
            return True

        if cmd == "session" and arg:
            self._session_id = arg.strip()
            self._reference_image = None
            print(f"[Info/信息] Switched to session: {self._session_id} / 已切换到会话: {self._session_id}")
            print("[Info/信息] Session reference image cleared on session switch / 切换会话后已清除参考图片")
            return True

        if cmd == "ref" and arg:
            ref_arg = arg.strip()
            if ref_arg.lower() == "clear":
                self._reference_image = None
                print("[Info/信息] Reference image cleared / 参考图片已清除")
                return True
            self._reference_image = ref_arg
            print(f"[Info/信息] Reference image set to: {self._reference_image}")
            print(f"[Info/信息] 参考图片已设置为: {self._reference_image}")
            print("           Use 'ref clear' to clear reference image / 使用 'ref clear' 清除参考图片")
            return True

        if cmd == "ref" and not arg:
            if self._reference_image:
                print(f"[Info/信息] Current reference image: {self._reference_image}")
                print(f"[Info/信息] 当前参考图片: {self._reference_image}")
            else:
                print("[Info/信息] No reference image set / 未设置参考图片")
            return True

        if cmd == "help":
            self._print_help()
            return True

        if handler:
            handler(self.service, self._session_id, arg)
            return True

        return False

    def run(self) -> None:
        """Main interactive loop.
        主交互循环。"""
        try:
            self._print_banner()
        except ConfigValidationError as e:
            print(f"[Config Error/配置错误] {e}")
            sys.exit(1)

        while True:
            try:
                user_input = input("Prompt/Command | 提示词/命令 > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye! / 再见！")
                break

            if not user_input:
                print("[Warning/警告] Prompt cannot be empty / 提示词不能为空")
                continue

            if self._handle_command(user_input):
                print("-" * 40)
                continue

            try:
                ref_image = None
                size = None
                parts = user_input.split()
                index = 0
                parse_error = False
                while index < len(parts):
                    token = parts[index]
                    if token == "--ref":
                        if index + 1 >= len(parts):
                            print("[Warning/警告] Missing value after --ref / --ref 后面缺少值")
                            print("-" * 40)
                            parse_error = True
                            break
                        ref_image = parts[index + 1]
                        index += 2
                        continue
                    if token == "--size":
                        if index + 1 >= len(parts):
                            print("[Warning/警告] Missing value after --size / --size 后面缺少值")
                            print("-" * 40)
                            parse_error = True
                            break
                        size = parts[index + 1]
                        index += 2
                        continue
                    break
                else:
                    if ref_image or size:
                        print("[Warning/警告] Missing prompt content / 缺少提示词内容")
                        print("-" * 40)
                        continue
                if parse_error:
                    continue
                if index >= len(parts):
                    continue
                user_input = " ".join(parts[index:])
                
                result = self.service.generate(
                    user_input, 
                    self._session_id,
                    size=size,
                    reference_image=ref_image or self._reference_image
                )

                if result:
                    print(f"[Complete/完成] Image generated: {result} / 图像已生成: {result}")
                else:
                    print("[Failed/失败] Generation failed. Please check API key and network.")
                    print("         生成过程出现问题，请检查 API 密钥和网络。")
            except Exception as e:
                print(f"[Error/错误] Unhandled exception: {e} / 未处理的异常: {e}")

            print("-" * 40)


def main() -> None:
    """Entry point for the CLI application.
    CLI 应用程序的入口点。"""
    try:
        with ImageGenerationService() as service:
            cli = CLI(service)
            cli.run()
    except ConfigValidationError as e:
        print(f"[Config Error/配置错误] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[Fatal Error/致命错误] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
