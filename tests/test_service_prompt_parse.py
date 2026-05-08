from image_generator.image_service import ImageGenerationService


def test_parse_prompt_extracts_image_tag():
    svc = ImageGenerationService()
    prompt, ref, size = svc._parse_prompt("[image:/tmp/ref.png] make it sunny")
    assert prompt == "make it sunny"
    assert ref == "/tmp/ref.png"
    assert size is None


def test_parse_prompt_extracts_size_auto():
    svc = ImageGenerationService()
    prompt, ref, size = svc._parse_prompt("[size:auto] draw skyline")
    assert prompt == "draw skyline"
    assert ref is None
    assert size == "auto"


def test_parse_prompt_extracts_size_1536x1024():
    svc = ImageGenerationService()
    prompt, ref, size = svc._parse_prompt("[size:1536x1024] draw skyline")
    assert prompt == "draw skyline"
    assert ref is None
    assert size == "1536x1024"


def test_parse_prompt_invalid_size_returns_none_and_keeps_prompt_clean():
    svc = ImageGenerationService()
    prompt, ref, size = svc._parse_prompt("[size:9999x9999] draw skyline")
    assert prompt == "draw skyline"
    assert ref is None
    assert size is None
