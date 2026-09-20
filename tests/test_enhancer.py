import pytest
from unittest.mock import patch
from enhance_this.enhancer import PromptEnhancer, load_templates

# Content expected by the tests (replaces the real template files).
BUILTIN_TEMPLATES = {
    "detailed.txt": "Detailed template: {user_prompt}",
    "concise.txt": "Concise template: {user_prompt}",
    "creative.txt": "Creative template: {user_prompt}",
    "technical.txt": "Technical template: {user_prompt}",
}


class _FakeTemplateFile:
    def __init__(self, name):
        self._name = name

    def read_text(self, encoding="utf-8"):
        if self._name not in BUILTIN_TEMPLATES:
            raise FileNotFoundError(self._name)
        return BUILTIN_TEMPLATES[self._name]


class _FakeTemplatesDir:
    def joinpath(self, relative):
        return _FakeTemplateFile(relative.split("/")[-1])


@pytest.fixture(autouse=True)
def mock_builtin_templates():
    """Replace importlib.resources.files with a minimal in-memory fake.

    Replicates the joinpath() -> name -> read_text() path that
    enhancer.load_templates exercises, and raises FileNotFoundError for
    undefined styles (which the code handles gracefully).
    """
    with patch("importlib.resources.files", return_value=_FakeTemplatesDir()):
        yield


def test_load_templates_builtin():
    templates = load_templates()
    assert "detailed" in templates
    assert "concise" in templates
    assert "creative" in templates
    assert "technical" in templates
    assert templates["detailed"] == "Detailed template: {user_prompt}"


def test_load_templates_with_custom_templates():
    from pathlib import Path
    import shutil
    import uuid

    # Scratch dir inside the workspace (tmp_path/tempfile are sandbox-blocked).
    scratch = Path("_enhtest") / uuid.uuid4().hex
    scratch.mkdir(parents=True)
    try:
        custom_template_file = scratch / "my_custom_template.txt"
        custom_template_file.write_text("My custom template: {user_prompt}")

        custom_template_paths = {
            "custom_style": str(custom_template_file),
            "detailed": str(custom_template_file),  # Override built-in
            "non_existent": str(scratch / "non_existent.txt"),  # Non-existent path
        }

        templates = load_templates(custom_template_paths)
        assert "custom_style" in templates
        assert templates["custom_style"] == "My custom template: {user_prompt}"
        assert templates["detailed"] == "My custom template: {user_prompt}"  # Check override
        assert "non_existent" not in templates  # Non-existent should not be loaded
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_prompt_enhancer_enhance():
    enhancer = PromptEnhancer()
    enhanced_prompt = enhancer.enhance("my simple prompt", "detailed")
    assert enhanced_prompt == "Detailed template: my simple prompt"


def test_prompt_enhancer_unknown_style():
    enhancer = PromptEnhancer()
    with pytest.raises(ValueError, match="Unknown style: 'unknown_style'"):
        enhancer.enhance("my simple prompt", "unknown_style")


def test_load_templates_with_invalid_custom_path_type():
    custom_template_paths = {
        "invalid_style": 123  # Not a string
    }
    templates = load_templates(custom_template_paths)
    assert "invalid_style" not in templates


def test_load_templates_with_empty_custom_path_string():
    custom_template_paths = {
        "empty_path_style": ""  # Empty string
    }
    templates = load_templates(custom_template_paths)
    assert "empty_path_style" not in templates