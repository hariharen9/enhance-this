import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from enhance_this.cli import enhance as main
from enhance_this import config


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_ollama_client():
    # Patch build_provider so no real network I/O ever happens during CLI tests.
    # The default config provider is "ollama", so build_provider is expected to
    # return a provider whose interface we stub here.
    with patch('enhance_this.cli.build_provider') as mock_build:
        instance = MagicMock()
        instance.name = "ollama"
        instance.is_available.return_value = True
        instance.list_models.return_value = ["llama2"]
        instance.download_model.return_value = True
        instance.generate_stream.return_value = iter(["Enhanced ", "Prompt"])
        # Pretend the ollama wrapper exposes itself as the underlying client so
        # _ollama_client_for() routes download/preload back onto this mock.
        instance.client = instance
        mock_build.return_value = instance
        yield instance


@pytest.fixture(autouse=True)
def mock_clipboard():
    # Patch the name as bound inside cli (from .clipboard import copy_to_clipboard).
    with patch('enhance_this.cli.copy_to_clipboard') as mock_copy:
        yield mock_copy


@pytest.fixture(autouse=True)
def mock_config_file():
    # Keep tests hermetic: route config + template reads/writes to a scratch
    # dir inside the workspace (the DSH sandbox blocks tempfile/tmp_path).
    from pathlib import Path
    import shutil
    import uuid

    test_config_dir = Path("_testcfg") / uuid.uuid4().hex
    test_config_dir.mkdir(parents=True)
    test_config_file = test_config_dir / "config.yaml"

    original_get_config_path = config.get_config_path
    original_get_config_dir = config.get_config_dir
    config.get_config_path = lambda *args, **kwargs: test_config_file
    config.get_config_dir = lambda: test_config_dir
    yield test_config_file
    config.get_config_path = original_get_config_path
    config.get_config_dir = original_get_config_dir
    shutil.rmtree(test_config_dir, ignore_errors=True)

    # Ensure a default config exists for tests that need one.
    config.create_default_config_if_not_exists()


def test_cli_version(runner):
    from enhance_this.version import __version__
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"enhance, version {__version__}"


def test_cli_help(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Usage: enhance [OPTIONS] [PROMPT]" in result.output


def test_cli_no_prompt(runner):
    result = runner.invoke(main, [])
    assert result.exit_code == 0  # Help message is shown, not an error
    assert "Usage: enhance [OPTIONS] [PROMPT]" in result.output


def test_cli_ollama_not_running(runner, mock_ollama_client):
    mock_ollama_client.is_available.return_value = False
    result = runner.invoke(main, ["test prompt"])
    assert result.exit_code == 1
    assert "Ollama service is not running or is unreachable." in result.output


def test_cli_list_models(runner, mock_ollama_client):
    mock_ollama_client.list_models.return_value = ["model1", "model2"]
    result = runner.invoke(main, ["--list-models"])
    assert result.exit_code == 0
    # The Rich table title may wrap in a non-TTY capture, so check rows only.
    assert "model1" in result.output
    assert "model2" in result.output


def test_cli_download_model(runner, mock_ollama_client):
    result = runner.invoke(main, ["--download-model", "new_model"])
    assert result.exit_code == 0
    mock_ollama_client.download_model.assert_called_once_with("new_model")
    assert "Starting download for 'new_model'..." in result.output


def test_cli_auto_setup_no_models(runner, mock_ollama_client):
    mock_ollama_client.list_models.return_value = []
    result = runner.invoke(main, ["--auto-setup"])
    assert result.exit_code == 0
    mock_ollama_client.download_model.assert_called_once_with("gemma3:4b")
    assert "No models found. Starting auto-setup." in result.output


def test_cli_auto_setup_model_exists(runner, mock_ollama_client):
    mock_ollama_client.list_models.return_value = ["gemma3:4b"]
    result = runner.invoke(main, ["--auto-setup"])
    assert result.exit_code == 0
    mock_ollama_client.download_model.assert_not_called()
    assert "Recommended model 'gemma3:4b' is already available." in result.output


def test_cli_enhance_success(runner, mock_ollama_client, mock_clipboard):
    result = runner.invoke(main, ["my test prompt"])
    assert result.exit_code == 0
    assert "✨ Enhanced Prompt ✨" in result.output
    assert "Enhanced Prompt" in result.output  # From the streamed output
    mock_ollama_client.generate_stream.assert_called_once()
    mock_clipboard.assert_called_once_with("Enhanced Prompt")


def test_cli_enhance_no_copy(runner, mock_ollama_client, mock_clipboard):
    result = runner.invoke(main, ["my test prompt", "-n"])
    assert result.exit_code == 0
    mock_clipboard.assert_not_called()


def test_cli_enhance_output_file(runner, mock_ollama_client):
    from pathlib import Path
    import shutil
    import uuid
    scratch = Path("_outtest") / uuid.uuid4().hex
    scratch.mkdir(parents=True)
    try:
        output_file = scratch / "output.txt"
        result = runner.invoke(main, ["my test prompt", "-o", str(output_file)])
        assert result.exit_code == 0
        assert "Saved to" in result.output
        assert output_file.read_text() == "Enhanced Prompt"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_cli_enhance_diff_view(runner, mock_ollama_client):
    mock_ollama_client.generate_stream.return_value = iter(["This is the ", "enhanced output."])
    result = runner.invoke(main, ["This is the original input.", "--diff"])
    assert result.exit_code == 0
    assert "↔️  Diff View ↔️" in result.output
    # difflib.unified_diff uses +/- prefixes without a trailing space.
    assert "-This is the original input." in result.output
    assert "+This is the enhanced output." in result.output


def test_cli_enhance_verbose(runner, mock_ollama_client):
    result = runner.invoke(main, ["my test prompt", "-v"])
    assert result.exit_code == 0
    assert "System Prompt:" in result.output
    mock_ollama_client.generate_stream.assert_called_once()


def test_cli_enhance_specific_model_not_found(runner, mock_ollama_client):
    mock_ollama_client.list_models.return_value = ["model_a"]
    result = runner.invoke(main, ["prompt", "-m", "non_existent_model"])
    assert result.exit_code == 1
    assert "Model 'non_existent_model' not found." in result.output


def test_cli_enhance_no_models_available(runner, mock_ollama_client):
    mock_ollama_client.list_models.return_value = []
    mock_ollama_client.download_model.return_value = False  # Simulate download failure
    result = runner.invoke(main, ["prompt"])
    assert result.exit_code == 1
    assert "Auto-setup failed" in result.output


def test_cli_enhance_custom_style(runner, mock_ollama_client, mock_config_file):
    # Create a custom template file
    custom_template_path = mock_config_file.parent / "custom_template.txt"
    custom_template_path.write_text("Custom template for: {user_prompt}")

    # Update the config file to include the custom template
    with open(mock_config_file, 'a') as f:
        f.write("\nenhancement_templates:\n  my_custom_style: " + str(custom_template_path) + "\n")

    result = runner.invoke(main, ["my prompt", "-s", "my_custom_style"])
    assert result.exit_code == 0
    mock_ollama_client.generate_stream.assert_called_once()
    assert "✨ Enhanced Prompt ✨" in result.output


# ---------------------------------------------------------------------------
# API-provider tests (overrrode the autouse ollama mock `mock_ollama_client`).
# ---------------------------------------------------------------------------

API_CONFIG = {
    'provider': 'ollama',           # --provider api overrides this
    'default_style': 'detailed',
    'default_temperature': 0.7,
    'max_tokens': 2000,
    'auto_copy': False,
    'display_colors': True,
    'enhancement_templates': {},
    'timeout': 30,
    'api_provider': 'openrouter',
    'api_base_url': 'https://openrouter.ai/api/v1',
    'api_key': 'sk-test',
    'api_model': '',
    'api_default_model': 'qwen/qwen3.8-27b:free',
    'preferred_models': [],
    'preferred_api_models': ['nvidia/nemotron-3.5-lightning:free'],
}


def _api_mock():
    instance = MagicMock()
    instance.name = 'api'
    instance.is_available.return_value = True
    instance.list_models.return_value = []
    instance.generate_stream.return_value = iter(["Enhanced ", "Prompt"])
    return instance


def test_cli_api_enhance_default_model(runner, mock_ollama_client):
    # Config provides a key; explicit --provider api should route through build_provider.
    mock_ollama_client.name = 'api'
    mock_ollama_client.list_models.return_value = []
    with patch('enhance_this.cli.load_config', return_value=API_CONFIG):
        result = runner.invoke(main, ["my prompt", "--provider", "api", "-n"])
    assert result.exit_code == 0
    assert "✨ Enhanced Prompt ✨" in result.output
    # No explicit / remembered model -> the cheap default.
    used_model = mock_ollama_client.generate_stream.call_args[0][0]
    assert used_model == "qwen/qwen3.8-27b:free"


def test_cli_api_enhance_explicit_model(runner, mock_ollama_client):
    mock_ollama_client.name = 'api'
    with patch('enhance_this.cli.load_config', return_value=API_CONFIG), \
         patch('enhance_this.cli.persist_provider_selection') as persist:
        result = runner.invoke(main,
                               ["my prompt", "--provider", "api",
                                "-m", "anthropic/claude-3.5-sonnet", "-n"])
    assert result.exit_code == 0
    used_model = mock_ollama_client.generate_stream.call_args[0][0]
    assert used_model == "anthropic/claude-3.5-sonnet"
    # Explicit model choice should be remembered.
    persist.assert_called_once()
    persist.call_args.kwargs['api_model'] == "anthropic/claude-3.5-sonnet"


def test_cli_api_missing_key(runner, mock_ollama_client):
    cfg = dict(API_CONFIG)
    cfg['api_key'] = ''
    with patch('enhance_this.cli.load_config', return_value=cfg):
        result = runner.invoke(main, ["my prompt", "--provider", "api"])
    assert result.exit_code == 1
    assert "No API key found" in result.output


def test_cli_api_connection_error(runner, mock_ollama_client):
    mock_ollama_client.name = 'api'
    mock_ollama_client.is_available.return_value = False
    with patch('enhance_this.cli.load_config', return_value=API_CONFIG):
        result = runner.invoke(main, ["my prompt", "--provider", "api"])
    assert result.exit_code == 1
    assert "API provider could not be reached" in result.output


def test_cli_download_model_rejected_for_api(runner, mock_ollama_client):
    # --download-model only applies to Ollama; for an api provider it must be rejected.
    mock_ollama_client.name = 'api'
    with patch('enhance_this.cli.load_config', return_value=API_CONFIG):
        result = runner.invoke(main, ["--download-model", "x", "--provider", "api"])
    assert result.exit_code == 1
    assert "--download-model only applies to the local Ollama provider." in result.output