# Configuration Guide

`enhance-this` is designed to be highly configurable to fit your workflow. Configuration is handled via a YAML file located at `~/.enhance-this/config.yaml`.

The first time you run the tool, it will automatically generate a default configuration file for you.

## Default Configuration

Here is the default `config.yaml` with explanations for each setting:

```yaml
# The default temperature for the AI model (0.0 to 2.0).
# Higher values (e.g., 1.2) make the output more random and creative.
# Lower values (e.g., 0.5) make it more focused and deterministic.
default_temperature: 0.7

# The default enhancement style to use if none is specified with the -s flag.
# Can be one of: detailed, concise, creative, technical, or any custom style.
default_style: "detailed"

# The backend that powers enhancement:
#   "ollama"  -> run models locally through Ollama (default)
#   "api"     -> use a hosted OpenAI-compatible API (OpenRouter, OpenAI,
#                Groq, Together, DeepSeek, Mistral, ...) with your own key.
# Choose it with `enhance --config-wizard`, set it below, or switch on the
# fly with `enhance --provider api`.
provider: "ollama"

# The host and port where your Ollama instance is running (provider: ollama).
ollama_host: "http://localhost:11434"

# --- API provider settings (only used when provider: "api") ---

# Which hosted provider defaults to use. One of: openrouter, openai, groq,
# together, deepseek, mistral. Any OpenAI-compatible endpoint can be used by
# setting api_base_url directly.
api_provider: "openrouter"

# The base URL for the OpenAI-compatible API. This is filled in automatically
# for known providers but can point anywhere.
api_base_url: "https://openrouter.ai/api/v1"

# Your API key. You can also set the matching environment variable instead
# (OPENROUTER_API_KEY, OPENAI_API_KEY, GROQ_API_KEY, TOGETHER_API_KEY,
# DEEPSEEK_API_KEY, MISTRAL_API_KEY, or ENHANCE_THIS_API_BASE_URL for a custom
# base URL). The config value takes precedence over the env var.
api_key: ""

# The last AI model you chose with `--model`; it is remembered here and used
# as the default on later runs. Leave empty to use api_default_model.
api_model: ""

# A suggested cheap/fast default model, used only until you pick one yourself.
api_default_model: "qwen/qwen3.8-27b:free"

# The timeout in seconds for network requests to the backend.
timeout: 30

# The maximum number of tokens (words/pieces of words) for the generated prompt.
max_tokens: 2000

# Whether to automatically copy the enhanced prompt to the clipboard.
# Set to false to disable.
auto_copy: true

# Whether to use rich, colorful output in the terminal.
# Set to false for monochrome output.
display_colors: true

# If true, the tool will automatically try to download a recommended model
# if it detects that no models are installed (Ollama provider only).
auto_download_model: true

# A dictionary for defining your own custom enhancement styles.
# The key is the style name (which you can use with the -s flag).
# The value is the absolute path to your template file.
enhancement_templates:
  my_style: "/path/to/your/custom_template.txt"
```

## Bring Your Own API Key

Running locally with Ollama is the default, but you can switch to any
OpenAI-compatible hosted API (OpenRouter, OpenAI, Groq, Together, DeepSeek,
Mistral, ...) using your own key. A cheap, fast model is plenty for prompt
enhancement, so hosted APIs are often quicker than Ollama on low-end machines.

**Quick start (OpenRouter):**

```bash
# One command: use OpenRouter with your key and pick a model once.
enhance "make this prompt better" --provider api --api-key sk-or-... \
  --model qwen/qwen3.8-27b:free --save-key
```

After that the provider, key, and last chosen model are remembered, so plain:

```bash
enhance "make this prompt better" --provider api
```

will reuse them. You can also set the key once in `~/.enhance-this/config.yaml`
(`api_key`) or via the `OPENROUTER_API_KEY` environment variable, then skip
`--api-key`.

**Switching providers on the fly** (and remembering the choice):

```bash
enhance --provider api "your prompt"          # use hosted API this time
enhance --provider ollama "your prompt"       # back to local
enhance --config-wizard                       # persist your preference
```

`--model` works the same for both providers. For the API provider, whatever you
pass with `--model` is remembered as the new default for next time. `--list-models`
lists the models for whichever provider you're on.

Notes:

- The API provider talks to `{api_base_url}/chat/completions` with standard
  streaming, so any OpenAI-compatible gateway works.
- Your key is stored in plain text in your local `config.yaml`. If you'd rather
  not store it, just use the environment variable instead and leave `api_key`
  empty.
- `--download-model`, `--auto-setup`, and `--preload-model` are Ollama-only;
  hosted APIs have nothing to download.

## Custom Enhancement Templates

You can extend `enhance-this` with your own prompt styles. 

1.  Create a text file for your template. This file should contain the logic for your prompt enhancement. Use the placeholder `{user_prompt}` where the user's original prompt should be inserted.

2.  Open your `config.yaml` file.

3.  Add a new entry under the `enhancement_templates` section. The key is the name you want to use for your style, and the value is the full path to your `.txt` file.

### Example Custom Template

Let's say you want a style that translates prompts into Zenesque koans. 

**File: `/Users/me/templates/zen.txt`**
```
The user seeks clarity. Their words are: "{user_prompt}"

Transform this earthly request into a koan that a wise master might pose to a student. The koan should be paradoxical, simple, and profound. It should not answer, but question the questioner.
```

**`config.yaml` entry:**
```yaml
enhancement_templates:
  zen: "/Users/me/templates/zen.txt"
```

Now you can use your custom style from the command line:

```bash
enhance "how do I become a better programmer?" -s zen
```
