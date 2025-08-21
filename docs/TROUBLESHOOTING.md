# Troubleshooting Guide

Here are solutions to some common issues you might encounter with `enhance-this`.

### Error: Ollama service is not running or is unreachable

- **Cause:** This is the most common error. It means that `enhance-this` could not connect to the Ollama AI service.
- **Solution:**
    1.  **Ensure Ollama is installed:** If you haven't already, download and install Ollama from [ollama.com](https://ollama.com).
    2.  **Ensure Ollama is running:** The Ollama application must be running in the background for the CLI to work. Open your Applications folder (or equivalent) and run Ollama.
    3.  **Check the Host:** By default, the tool tries to connect to `http://localhost:11434`. If you have configured Ollama to run on a different address or port, you must update the `ollama_host` setting in your `~/.enhance-this/config.yaml` file.

### Error: No models available

- **Cause:** The tool has connected to Ollama, but your Ollama instance has no models downloaded.
- **Solution:**
    1.  **Run Auto-Setup:** The easiest fix is to run `enhance --auto-setup`. This will download a recommended, general-purpose model for you.
    2.  **Download a Model Manually:** You can see a list of available models to download on the [Ollama Library](https://ollama.com/library). Once you pick one, use the `download-model` command:
        ```bash
        enhance --download-model <model_name:tag>
        # Example:
        enhance --download-model "llama3.1:8b"
        ```

### Error: Could not copy to clipboard

- **Cause:** The tool could not access your system's clipboard. This is most common on Linux.
- **Solution (Linux):** You need to have a clipboard utility installed. You can install one using your package manager:
    ```bash
    # For Debian/Ubuntu
    sudo apt-get install xclip

    # For Fedora/CentOS
    sudo yum install xclip
    ```
- **Workaround:** You can always use the `-o <filename>` option to save the output directly to a file, or use the `--no-copy` (`-n`) flag to prevent the tool from trying to access the clipboard.

### The `--diff` view looks strange or is hard to read

- **Cause:** The diff view depends on your terminal's color support and font.
- **Solution:**
    1.  Ensure you are using a modern terminal application.
    2.  If the colors are the issue, you can disable them by setting `display_colors: false` in your `config.yaml`.

### My custom template is not being used

- **Cause:** The tool cannot find or read your custom template file.
- **Solution:**
    1.  **Check the Path:** Make sure the path in your `config.yaml` is the **full, absolute path** to your template file. Relative paths (`~/...`) are supported, but double-check them for typos.
    2.  **Check Permissions:** Ensure that you have read permissions for the template file.
    3.  **Check the Style Name:** Make sure the style name you are using with the `-s` flag exactly matches the key you defined in the `enhancement_templates` section of your config.
