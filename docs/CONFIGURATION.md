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

# The host and port where your Ollama instance is running.
ollama_host: "http://localhost:11434"

# The timeout in seconds for network requests to the Ollama API.
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
# if it detects that no models are installed.
auto_download_model: true

# A dictionary for defining your own custom enhancement styles.
# The key is the style name (which you can use with the -s flag).
# The value is the absolute path to your template file.
enhancement_templates:
  my_style: "/path/to/your/custom_template.txt"
```

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
