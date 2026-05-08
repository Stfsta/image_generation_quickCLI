from types import SimpleNamespace

from image_generator.cli import CLI


class DummyService:
    def __init__(self):
        self.config = SimpleNamespace(image_dir="generated_images")
        self.calls = []

    def clear_history(self, session_id):
        self.calls.append(("clear_history", {"session_id": session_id}))

    def generate(self, *args, **kwargs):
        self.calls.append(("generate", {"args": args, "kwargs": kwargs}))
        return "ok.png"


def test_cli_ref_command_set_and_clear():
    svc = DummyService()
    cli = CLI(svc)
    cli._handle_command("ref /tmp/ref.png")
    assert cli._reference_image == "/tmp/ref.png"
    cli._handle_command("ref clear")
    assert cli._reference_image is None


def test_cli_session_switch_clears_ref():
    svc = DummyService()
    cli = CLI(svc)
    cli._handle_command("ref /tmp/ref.png")
    cli._handle_command("session abc")
    assert cli._session_id == "abc"
    assert cli._reference_image is None


def test_cli_session_without_arg_shows_current_session(capsys):
    svc = DummyService()
    cli = CLI(svc)
    handled = cli._handle_command("session")
    out = capsys.readouterr().out
    assert handled is True
    assert "Current session ID" in out


def test_cli_prefers_inline_ref_over_session_ref(monkeypatch):
    svc = DummyService()
    cli = CLI(svc)
    cli._reference_image = "/tmp/session.png"
    inputs = iter(["--ref /tmp/inline.png hello"])

    def fake_input(_=""):
        try:
            return next(inputs)
        except StopIteration:
            raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", fake_input)
    cli.run()
    kwargs = svc.calls[0][1]["kwargs"]
    assert kwargs["reference_image"] == "/tmp/inline.png"


def test_cli_parses_size_flag(monkeypatch):
    svc = DummyService()
    cli = CLI(svc)
    inputs = iter(["--size 1536x1024 hello"])

    def fake_input(_=""):
        try:
            return next(inputs)
        except StopIteration:
            raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", fake_input)
    cli.run()
    kwargs = svc.calls[0][1]["kwargs"]
    assert kwargs["size"] == "1536x1024"


def test_cli_missing_flag_value_warns_and_skips_generation(monkeypatch):
    svc = DummyService()
    cli = CLI(svc)
    inputs = iter(["--size"])

    def fake_input(_=""):
        try:
            return next(inputs)
        except StopIteration:
            raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", fake_input)
    cli.run()
    assert not any(name == "generate" for name, _ in svc.calls)
