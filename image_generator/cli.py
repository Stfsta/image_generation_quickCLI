"""
Command-line interface with enhanced UX and command parsing.
命令行界面，支持增强的用户体验和命令解析。
"""

import sys
from pathlib import Path

from . import __version__
from .image_service import ImageGenerationService
from .config import ConfigValidationError
from .i18n import text


class CLI:
    """
    Interactive command-line interface for the image generation tool.
    Supports commands for history management, configuration reload, and help.
    图像生成工具的交互式命令行界面。
    支持历史管理、配置重新加载和帮助等命令。
    """

    COMMAND_ALIASES = ("lang", "language")

    def __init__(self, service: ImageGenerationService | None = None) -> None:
        self._service = service
        self._session_id = "default"
        self._reference_image = None

    @property
    def language(self) -> str:
        return self.service.language

    def _command_descriptions(self) -> dict[str, str]:
        return {
            "exit": text(self.language, "cmd_desc_exit"),
            "quit": text(self.language, "cmd_desc_exit"),
            "q": text(self.language, "cmd_desc_exit"),
            "clear": text(self.language, "cmd_desc_clear"),
            "session": text(self.language, "cmd_desc_session"),
            "help": text(self.language, "cmd_desc_help"),
            "ref": text(self.language, "cmd_desc_ref"),
            "lang": text(self.language, "cmd_desc_lang"),
            "language": text(self.language, "cmd_desc_lang"),
        }

    @property
    def service(self) -> ImageGenerationService:
        if self._service is None:
            self._service = ImageGenerationService()
        return self._service

    def _print_banner(self) -> None:
        image_dir = Path(self.service.config.image_dir)
        reference_dir = Path(self.service.config.reference_dir)
        print("\n" + "=" * 60)
        print(f"    {text(self.language, 'banner_title', version=__version__)}")
        print("=" * 60)
        print(text(self.language, "banner_usage"))
        print(text(self.language, "banner_item_prompt_or_command"))
        print(text(self.language, "banner_item_refine"))
        print(text(self.language, "banner_item_png_edits"))
        print(text(self.language, "banner_item_exit"))
        print(text(self.language, "banner_item_clear"))
        print(text(self.language, "banner_item_session"))
        print(text(self.language, "banner_item_session_switch"))
        print(text(self.language, "banner_item_help"))
        print(text(self.language, "banner_item_lang"))
        print(text(self.language, "banner_image_dir", path=image_dir.absolute()))
        print(text(self.language, "banner_reference_dir", path=reference_dir.absolute()))
        print("-" * 60)
        print(text(self.language, "banner_current_session", session_id=self._session_id) + "\n")

    def _print_help(self) -> None:
        print("\n" + text(self.language, "help_title"))
        for cmd, desc in self._command_descriptions().items():
            print(f"  {cmd:<10} - {desc}")
        print(text(self.language, "help_prompt_entry"))
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

        command_desc = self._command_descriptions()
        if cmd not in command_desc:
            return False

        if cmd == "session" and not arg:
            print(text(self.language, "info_current_session", session_id=self._session_id))
            return True

        if cmd == "session" and arg:
            self._session_id = arg.strip()
            self._reference_image = None
            print(text(self.language, "info_switched_session", session_id=self._session_id))
            print(text(self.language, "info_session_ref_cleared"))
            return True

        if cmd == "ref" and arg:
            ref_arg = arg.strip()
            if ref_arg.lower() == "clear":
                self._reference_image = None
                print(text(self.language, "info_ref_cleared"))
                return True
            self._reference_image = ref_arg
            print(text(self.language, "info_ref_set", reference=self._reference_image))
            print(text(self.language, "info_ref_hint_clear"))
            return True

        if cmd == "ref" and not arg:
            if self._reference_image:
                print(text(self.language, "info_current_ref", reference=self._reference_image))
            else:
                print(text(self.language, "info_no_ref"))
            return True

        if cmd == "help":
            self._print_help()
            return True

        if cmd in self.COMMAND_ALIASES:
            if not arg:
                print(text(self.language, "info_current_lang", code=self.language))
                return True
            target = arg.strip().lower()
            if target not in {"en", "zh"}:
                print(text(self.language, "warn_invalid_lang", value=target))
                return True
            self.service.set_language(target)
            print(text(self.language, "info_lang_switched", code=self.language))
            return True

        if cmd in {"exit", "quit", "q"}:
            sys.exit(0)

        if cmd == "clear":
            self.service.clear_history(self._session_id)
            return True

        return False

    def run(self) -> None:
        """Main interactive loop.
        主交互循环。"""
        try:
            self._print_banner()
        except ConfigValidationError as e:
            print(text("en", "result_config_error", error=e))
            sys.exit(1)

        while True:
            try:
                user_input = input(text(self.language, "prompt_input")).strip()
            except (EOFError, KeyboardInterrupt):
                print(text(self.language, "result_goodbye"))
                break

            if not user_input:
                print(text(self.language, "warn_prompt_empty"))
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
                            print(text(self.language, "warn_missing_ref_value"))
                            print("-" * 40)
                            parse_error = True
                            break
                        ref_image = parts[index + 1]
                        index += 2
                        continue
                    if token == "--size":
                        if index + 1 >= len(parts):
                            print(text(self.language, "warn_missing_size_value"))
                            print("-" * 40)
                            parse_error = True
                            break
                        size = parts[index + 1]
                        index += 2
                        continue
                    break
                else:
                    if ref_image or size:
                        print(text(self.language, "warn_missing_prompt_after_flags"))
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
                    print(text(self.language, "result_complete", path=result))
                else:
                    print(text(self.language, "result_failed"))
            except Exception as e:
                print(text(self.language, "result_unhandled", error=e))

            print("-" * 40)


def main() -> None:
    """Entry point for the CLI application.
    CLI 应用程序的入口点。"""
    try:
        with ImageGenerationService() as service:
            cli = CLI(service)
            cli.run()
    except ConfigValidationError as e:
        print(text("en", "result_config_error", error=e))
        sys.exit(1)
    except Exception as e:
        print(text("en", "result_fatal_error", error=e))
        sys.exit(1)


if __name__ == "__main__":
    main()
