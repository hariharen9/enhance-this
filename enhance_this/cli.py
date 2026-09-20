import click
import questionary
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
import sys
import difflib
import time
import random

from .config import load_config, create_default_config_if_not_exists, DEFAULT_CONFIG
from .version import __version__
from .provider_manager import (
    build_provider,
    resolve_api_model,
    persist_provider_selection,
    NoProviderConfiguredError,
)
from .providers.base import (
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderAuthError,
)
from .enhancer import PromptEnhancer
from .clipboard import copy_to_clipboard
from .history import save_enhancement, load_history

PROVIDER_CHOICES = ["ollama", "api"]
API_PROVIDER_NAMES = ["openrouter", "openai", "groq", "together", "deepseek", "mistral"]
OLLAMA_MODEL_NAMES = ["gemma3:4b", "gemma3:1b", "llama3.1:8b", "llama3", "mistral"]


def _provider_label(provider: str) -> str:
    return "Ollama (local)" if provider == "ollama" else "API (bring your own key)"


def _ollama_client_for(provider):
    """Return the underlying OllamaClient when provider is a local Ollama
    backend (to reach Ollama-only features like download/preload), else None."""
    if getattr(provider, "name", None) == "ollama":
        return getattr(provider, "client", None)
    return None


def _ollama_connection_help(host: str) -> str:
    return (
        "[bold]Troubleshooting steps:[/bold]\n"
        "1. Make sure Ollama is installed: [link]https://ollama.com/download[/link]\n"
        "2. Start Ollama service: [cyan]ollama serve[/cyan]\n"
        "3. Verify it's running: [cyan]curl http://localhost:11434[/cyan]\n\n"
        "[yellow]Tip:[/yellow] On first run, try [cyan]enhance --auto-setup[/cyan] to automatically set up Ollama.\n"
        "[yellow]Or switch to a hosted API:[/yellow] [cyan]enhance --provider api --api-key <key>[/cyan]"
    )


def _api_connection_help() -> str:
    return (
        "[bold]To use an API provider you need a key.[/bold]\n"
        "1. Get a key from your provider (e.g. [link]https://openrouter.ai[/link])\n"
        "2. Set it in [cyan]~/.enhance-this/config.yaml[/cyan] under [cyan]api_key[/cyan], or run:\n"
        "   [cyan]enhance --provider api --api-key sk-...[/cyan]\n"
        "3. Or export it: [cyan]set OPENROUTER_API_KEY=sk-...[/cyan]"
    )


@click.command()
@click.argument('prompt', required=False)
@click.option('-m', '--model', 'model_name', help='Model to use (auto-selects optimal if not specified)')
@click.option('-t', '--temperature', type=click.FloatRange(0.0, 2.0), help='Temperature for generation (0.0-2.0)')
@click.option('-l', '--length', 'max_tokens', type=int, help='Max tokens for enhancement')
@click.option('-c', '--config', 'config_path', type=click.Path(), help='Configuration file path')
@click.option('-v', '--verbose', is_flag=True, help='Enable verbose output')
@click.option('-n', '--no-copy', is_flag=True, help="Don't copy to clipboard")
@click.option('-o', '--output', 'output_file', type=click.File('w'), help='Save enhanced prompt to file')
@click.option('-s', '--style', type=click.STRING, help='Enhancement style (built-in or custom)')
@click.option('--diff', is_flag=True, help='Show a diff between the original and enhanced prompt')
@click.option('--provider', 'provider_name', type=click.Choice(PROVIDER_CHOICES), help='Backend provider: ollama (local) or api (bring your own key). Persisted in config.')
@click.option('--api-key', 'api_key', help='API key for the api provider (session override; persisted if --save-key is used).')
@click.option('--save-key', is_flag=True, help='Persist --api-key into the config file.')
@click.option('--api-base-url', 'api_base_url', help='Base URL for the api provider (session override).')
@click.option('--list-models', is_flag=True, help='List available models for the active provider')
@click.option('--download-model', 'download_model_name', help='Download specific model from Ollama (local only)')
@click.option('--auto-setup', is_flag=True, help='Automatically setup Ollama with optimal model')
@click.option('--history', 'show_history', is_flag=True, help='Show enhancement history.')
@click.option('--interactive', 'is_interactive', is_flag=True, help='Start an interactive enhancement session.')
@click.option('--preload-model', is_flag=True, help='Preload a model to keep it in memory for faster responses (local only).')
@click.option('--config-wizard', is_flag=True, help='Run the configuration wizard for first-time setup.')
@click.option('--template-editor', is_flag=True, help='Launch the visual template editor.')
@click.version_option(version=__version__)
@click.help_option('-h', '--help')
def enhance(prompt, model_name, temperature, max_tokens, config_path, verbose, no_copy, output_file, style, diff, provider_name, api_key, save_key, api_base_url, list_models, download_model_name, auto_setup, show_history, is_interactive, preload_model, config_wizard, template_editor):
    """
    Enhances a simple prompt using an AI backend (local Ollama or a hosted API
    like OpenRouter/OpenAI with your own key), displays the enhanced version,
    and automatically copies it to the clipboard.

    Choose a backend with --provider, and pick a model with --model. Your pick
    is remembered for the API provider across runs.

    Configuration Wizard:
      Run 'enhance --config-wizard' to set up enhance-this interactively.

    Template Editor:
      Run 'enhance --template-editor' to create and edit custom prompt templates.

    Note: Response speed and quality depend on your chosen backend/model.
    """
    console = Console()
    config = load_config(config_path)

    # Determine effective provider: CLI flag wins, else config.
    effective_provider = (provider_name or config.get('provider') or 'ollama').lower().strip()
    if effective_provider not in ("ollama", "api"):
        console.print(Panel(
            f"[red]✖ Unknown provider '{effective_provider}'.[/red]",
            title="Provider Error",
            border_style="red",
        ))
        sys.exit(1)

    # Apply any session-only api overrides before building the client.
    if api_key is not None:
        config['api_key'] = api_key
    if api_base_url is not None:
        config['api_base_url'] = api_base_url

    # Persist the key when explicitly asked to.
    if save_key:
        persist_provider_selection(
            config_path,
            api_key=config.get('api_key'),
            api_base_url=config.get('api_base_url'),
        )
        console.print("[green]✔[/green] API key saved to config.")

    # Build the active provider client.
    if effective_provider == "api":
        from .providers.openai_compatible import resolve_api_config
        resolved = resolve_api_config(config)
        if not resolved["api_key"]:
            console.print(Panel(
                "[red]✖ No API key found.[/red]\n\n" + _api_connection_help(),
                title="API Key Missing",
                border_style="red",
            ))
            sys.exit(1)
    try:
        client = build_provider(config, provider=effective_provider)
    except NoProviderConfiguredError as e:
        console.print(Panel(f"[red]✖ {e}[/red]", title="Provider Error", border_style="red"))
        sys.exit(1)

    # Handle configuration wizard
    if config_wizard:
        run_config_wizard(console, config_path)
        return

    # Handle template editor
    if template_editor:
        run_template_editor(console, config)
        return

    if preload_model:
        oclient = _ollama_client_for(client)
        if oclient is None:
            console.print("[red]✖ --preload-model only applies to the local Ollama provider.[/red]")
            sys.exit(1)
        available_models = oclient.list_models()
        if not available_models:
            console.print("[red]✖[/red] No models available to preload. Please run [bold]`enhance --auto-setup`[/bold] first.")
            sys.exit(1)

        preferred_models = config.get('preferred_models', OLLAMA_MODEL_NAMES)
        model_to_preload = None
        for model in preferred_models:
            if model in available_models:
                model_to_preload = model
                break

        if not model_to_preload:
            model_to_preload = available_models[0]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Preloading model '{model_to_preload}'...", total=None)
            oclient.preload_model(model_to_preload)
            progress.update(task, description=f"[green]✔ Model '{model_to_preload}' preloaded successfully!")
            time.sleep(1)
        return

    if show_history:
        history_entries = load_history()
        if not history_entries:
            console.print(Panel("[yellow]No history found.[/yellow]", title="History", border_style="yellow"))
            return

        choices = [
            {
                'name': f"{entry['original_prompt']} -> {entry['enhanced_prompt'][:50]}...",
                'value': entry
            }
            for entry in history_entries
        ]

        selected_entry = questionary.select(
            "Select a history entry to view:",
            choices=choices
        ).ask()

        if selected_entry:
            history_table = Table(title="History Details", border_style="green")
            history_table.add_column("Property", style="cyan", no_wrap=True)
            history_table.add_column("Value", style="magenta")

            history_table.add_row("Original Prompt", selected_entry['original_prompt'])
            history_table.add_row("Enhanced Prompt", selected_entry['enhanced_prompt'])
            history_table.add_row("Style", selected_entry['style'])
            history_table.add_row("Model", selected_entry['model'])

            console.print(history_table)

            if questionary.confirm("Copy enhanced prompt to clipboard?").ask():
                copy_to_clipboard(selected_entry['enhanced_prompt'])
                console.print("[green]✔ Copied to clipboard.[/green]")
        return

    if is_interactive:
        welcome_panel = Panel(
            "[bold green]Welcome to Interactive Mode![/bold green]\n"
            "Enhance your prompts in real-time with AI assistance.\n"
            f"[dim]Provider: {_provider_label(effective_provider)} | Type 'quit' or 'exit' to end the session.[/dim]",
            title="✨ Enhance This - Interactive Mode",
            border_style="bright_blue"
        )
        console.print(welcome_panel)

        enhancer = PromptEnhancer(config.get('enhancement_templates'))
        available_styles = list(enhancer.templates.keys())

        try:
            if not client.is_available():
                if effective_provider == "ollama":
                    console.print(Panel(
                        "[red]✖ Ollama service is not running or is unreachable.[/red]\n\n"
                        + _ollama_connection_help(config.get('ollama_host', DEFAULT_CONFIG['ollama_host'])),
                        title="Connection Error",
                        border_style="red"
                    ))
                else:
                    console.print(Panel(
                        "[red]✖ API provider could not be reached with the configured key.[/red]\n\n"
                        + _api_connection_help(),
                        title="Connection Error",
                        border_style="red"
                    ))
                sys.exit(1)
        except Exception as e:
            console.print(Panel(
                f"[red]✖ Unexpected error while checking provider connection:[/red]\n{str(e)}",
                title="Connection Error",
                border_style="red"
            ))
            sys.exit(1)

        try:
            available_models = client.list_models()
        except Exception as e:
            console.print(Panel(
                f"[red]✖ Error retrieving model list:[/red]\n{str(e)}",
                title="Model Error",
                border_style="red"
            ))
            available_models = []

        # For Ollama, require at least one local model installed.
        if effective_provider == "ollama" and not available_models:
            console.print(Panel(
                "[red]✖ No models available.[/red]\n\n"
                "[bold]To resolve this:[/bold]\n"
                "1. Run [cyan]enhance --auto-setup[/cyan] (recommended)\n"
                "2. Or manually install a model: [cyan]ollama pull llama3.1:8b[/cyan]",
                title="Model Error",
                border_style="red"
            ))
            sys.exit(1)

        final_model = _pick_model(
            effective_provider, client, config, model_name, available_models
        )
        if final_model is None:
            sys.exit(1)

        console.print(f"[bold blue]🤖 Using model:[/bold blue] [cyan]{final_model}[/cyan]")

        current_prompt = ""
        enhanced_prompt = ""
        current_style = config.get('default_style', 'detailed')

        while True:
            try:
                if not current_prompt:
                    current_prompt = console.input("[bold cyan]Enter initial prompt: [/bold cyan]")
                    if current_prompt.lower() in ['quit', 'exit']:
                        break

                system_prompt = enhancer.enhance(current_prompt, current_style)

                try:
                    enhanced_prompt = _stream_generate_with_live(
                        client, final_model, system_prompt, 0.7, 2000, console,
                        spinner_name="dots9", content_style="magenta",
                    )
                except ProviderConnectionError:
                    console.print(Panel(
                        f"[red]✖ Connection error with {_provider_label(effective_provider)}.[/red]\n"
                        "[yellow]Please check the backend is reachable and try again.[/yellow]",
                        title="Connection Error",
                        border_style="red"
                    ))
                    continue
                except ProviderTimeoutError:
                    console.print(Panel(
                        "[red]✖ Request timed out.[/red]\n"
                        "[yellow]The model may still be loading. Please try again.[/yellow]",
                        title="Timeout Error",
                        border_style="red"
                    ))
                    continue
                except ProviderAuthError:
                    console.print(Panel(
                        "[red]✖ API key was rejected.[/red]\n\n" + _api_connection_help(),
                        title="Auth Error",
                        border_style="red"
                    ))
                    continue
                except KeyboardInterrupt:
                    console.print(Panel(
                        "[yellow]⚠ Operation cancelled by user.[/yellow]\n\n"
                        "[dim]You can resume your session later.[/dim]",
                        title="Cancelled",
                        border_style="yellow"
                    ))
                    break

                console.print("\n[bold magenta]✨ Enhanced Prompt ✨[/bold magenta]")
                console.print(Panel(Markdown(enhanced_prompt), 
                                  title="Enhanced Output", 
                                  border_style="green",
                                  expand=False))

                action = console.input(
                    "[bold blue]Choose action:[/bold blue] "
                    "[bold](r)[/bold]efine, "
                    "[bold](s)[/bold]tyle, "
                    "[bold](c)[/bold]opy, "
                    "[bold](q)[/bold]uit: "
                ).lower()

                if action == 'r':
                    current_prompt = console.input("[bold cyan]Refine prompt: [/bold cyan]")
                elif action == 's':
                    console.print(f"[bold blue]Available styles:[/bold blue] {', '.join(available_styles)}")
                    new_style = console.input(f"[bold cyan]New style ({current_style}): [/bold cyan]")
                    if new_style in available_styles:
                        current_style = new_style
                    elif new_style:
                        console.print(f"[yellow]Invalid style. Sticking with {current_style}.[/yellow]")
                elif action == 'c':
                    try:
                        copy_to_clipboard(enhanced_prompt)
                    except Exception as e:
                        console.print(Panel(
                            f"[red]✖ Error copying to clipboard:[/red]\n{str(e)}\n\n"
                            f"[yellow]You can manually copy the prompt above.[/yellow]",
                            title="Clipboard Error",
                            border_style="red"
                        ))
                elif action == 'q':
                    break
                else:
                    console.print("[yellow]Invalid action.[/yellow]")

            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                break
            except Exception as e:
                console.print(Panel(
                    f"[red]✖ Unexpected error in interactive mode:[/red]\n{str(e)}\n\n"
                    f"[yellow]Continuing session...[/yellow]",
                    title="Interactive Mode Error",
                    border_style="red"
                ))

        console.print(Panel("[bold green]Exiting interactive mode. Goodbye![/bold green] 👋", 
                          title="Session Ended", border_style="green"))
        return

    create_default_config_if_not_exists()

    # Connection check for the non-interactive path.
    try:
        if not client.is_available():
            if effective_provider == "ollama":
                console.print(Panel(
                    "[red]✖ Ollama service is not running or is unreachable.[/red]\n\n"
                    + _ollama_connection_help(config.get('ollama_host', DEFAULT_CONFIG['ollama_host'])),
                    title="Connection Error",
                    border_style="red"
                ))
            else:
                console.print(Panel(
                    "[red]✖ API provider could not be reached with the configured key.[/red]\n\n"
                    + _api_connection_help(),
                    title="Connection Error",
                    border_style="red"
                ))
            sys.exit(1)
    except Exception as e:
        console.print(Panel(
            f"[red]✖ Unexpected error while checking provider connection:[/red]\n{str(e)}\n\n"
            "[yellow]Please check your network connection and configuration.[/yellow]",
            title="Connection Error",
            border_style="red"
        ))
        sys.exit(1)

    if list_models:
        try:
            models = client.list_models()
            if models:
                if effective_provider == "api":
                    models_table = Table(title=f"Available {effective_provider} Models", border_style="green")
                else:
                    models_table = Table(title="Available Ollama Models", border_style="green")
                models_table.add_column("Model Name", style="cyan")
                for model in models:
                    models_table.add_row(model)
                console.print(models_table)
            else:
                if effective_provider == "ollama":
                    console.print(Panel(
                        "[yellow]No Ollama models found.[/yellow]\n\n"
                        "[bold]To install a model:[/bold]\n"
                        "• Run [cyan]enhance --auto-setup[/cyan] (recommended)\n"
                        "• Or manually install: [cyan]ollama pull llama3.1:8b[/cyan]",
                        title="Models",
                        border_style="yellow"
                    ))
                else:
                    console.print(Panel(
                        "[yellow]No models could be listed from the API provider.[/yellow]\n\n"
                        "[dim]You can still use [cyan]--model <name>[/cyan] directly; the provider will validate it.[/dim]",
                        title="Models",
                        border_style="yellow"
                    ))
        except Exception as e:
            console.print(Panel(
                f"[red]✖ Error listing models:[/red]\n{str(e)}",
                title="Model Error",
                border_style="red"
            ))
        return

    if download_model_name:
        oclient = _ollama_client_for(client)
        if oclient is None:
            console.print("[red]✖ --download-model only applies to the local Ollama provider.[/red]")
            sys.exit(1)
        console.print(f"[bold blue]📥 Starting download for '{download_model_name}'...[/bold blue]")
        try:
            success = oclient.download_model(download_model_name)
            if not success:
                console.print(Panel(
                    f"[red]✖ Failed to download model '{download_model_name}'.[/red]\n\n"
                    "[bold]Troubleshooting:[/bold]\n"
                    "• Check model name spelling\n"
                    "• Ensure internet connection\n"
                    "• Verify Ollama is running",
                    title="Download Error",
                    border_style="red"
                ))
        except Exception as e:
            console.print(Panel(
                f"[red]✖ Unexpected error downloading model:[/red]\n{str(e)}",
                title="Download Error",
                border_style="red"
            ))
        return

    available_models = []
    try:
        available_models = client.list_models()
    except Exception as e:
        console.print(Panel(
            f"[red]✖ Error retrieving model list:[/red]\n{str(e)}\n\n"
            "[yellow]Continuing...[/yellow]",
            title="Model Error",
            border_style="yellow"
        ))

    # Auto-setup / model download is an Ollama-only concept.
    if effective_provider == "ollama" and (auto_setup or not available_models):
        if not available_models:
            console.print(Panel(
                "[yellow]No models found. Starting auto-setup.[/yellow]\n"
                "[dim]This may take a few minutes to download the recommended model.[/dim]",
                title="Setup",
                border_style="yellow"
            ))
        else:
            console.print("[bold blue]Starting auto-setup...[/bold blue]")

        recommended_models = config.get('preferred_models', OLLAMA_MODEL_NAMES)
        oclient = _ollama_client_for(client)
        model_installed = False

        for model_to_try in recommended_models:
            try:
                if model_to_try not in available_models:
                    console.print(f"[bold blue]📥 Downloading recommended model:[/bold blue] [cyan]{model_to_try}[/cyan]")
                    if oclient and oclient.download_model(model_to_try):
                        available_models.append(model_to_try)
                        model_installed = True
                        break 
                else:
                    console.print(f"[green]✔[/green] Recommended model '[cyan]{model_to_try}[/cyan]' is already available.")
                    model_installed = True
                    break
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Error with model {model_to_try}: {e}")
                continue

        if not model_installed:
            console.print(Panel(
                "[red]✖ Auto-setup failed. Could not download a recommended model.[/red]\n\n"
                "[bold]Manual steps:[/bold]\n"
                "1. Check internet connection\n"
                "2. Try manually: [cyan]ollama pull llama3.1:8b[/cyan]\n"
                "3. Or visit: [link]https://ollama.com/library[/link]",
                title="Setup Error",
                border_style="red"
            ))
            sys.exit(1)

        if auto_setup:
            return

    if not prompt:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()

    final_model = _pick_model(
        effective_provider, client, config, model_name, available_models
    )
    if final_model is None:
        sys.exit(1)

    # Remember the chosen API model so it is used next time by default.
    if effective_provider == "api" and model_name:
        persist_provider_selection(config_path, api_model=model_name)

    if verbose and model_name is None:
        console.print(f"[bold blue]No model specified.[/bold blue] Using best available model: [cyan]{final_model}[/cyan]")

    final_style = style or config.get('default_style', 'detailed')
    final_temperature = temperature if temperature is not None else config.get('default_temperature', 0.7)
    final_max_tokens = max_tokens or config.get('max_tokens', 2000)
    auto_copy_enabled = not no_copy and config.get('auto_copy', True)

    enhancer = PromptEnhancer(config.get('enhancement_templates'))

    if final_style not in enhancer.templates:
        console.print(Panel(
            f"[red]✖ Unknown style '{final_style}'.[/red]\n\n"
            f"[bold]Available styles:[/bold] {', '.join(sorted(enhancer.templates))}",
            title="Style Error",
            border_style="red"
        ))
        sys.exit(1)

    system_prompt = enhancer.enhance(prompt, final_style)

    if verbose:
        console.print("\n[bold blue]🔧 System Prompt:[/bold blue]")
        console.print(Panel(system_prompt, title="System Prompt", border_style="dim"))

    console.print("[bold blue]🤖 Generating enhanced prompt...[/bold blue]")

    try:
        enhanced_prompt = _stream_generate_with_live(
            client, final_model, system_prompt, final_temperature, final_max_tokens, console
        )
    except ProviderConnectionError:
        if effective_provider == "ollama":
            console.print(Panel(
                "[red]✖ Connection error with Ollama service.[/red]\n\n"
                + _ollama_connection_help(config.get('ollama_host', DEFAULT_CONFIG['ollama_host'])),
                title="Connection Error",
                border_style="red"
            ))
        else:
            console.print(Panel(
                "[red]✖ Connection error with API provider.[/red]\n\n" + _api_connection_help(),
                title="Connection Error",
                border_style="red"
            ))
        sys.exit(1)
    except ProviderTimeoutError:
        console.print(Panel(
            f"[red]✖ Request timed out while communicating with {_provider_label(effective_provider)}.[/red]\n\n"
            "[yellow]This might happen if:[/yellow]\n"
            "• The model is still loading\n"
            "• The prompt is very complex\n"
            "• Your system is under heavy load\n\n"
            "[bold]Try:[/bold]\n"
            "• Increasing timeout in config (~/.enhance-this/config.yaml)\n"
            "• Using a smaller model",
            title="Timeout Error",
            border_style="red"
        ))
        sys.exit(1)
    except ProviderAuthError:
        console.print(Panel(
            "[red]✖ API key was rejected.[/red]\n\n" + _api_connection_help(),
            title="Auth Error",
            border_style="red"
        ))
        sys.exit(1)
    except KeyboardInterrupt:
        console.print(Panel(
            "[yellow]⚠ Operation cancelled by user.[/yellow]\n\n"
            "[dim]You can resume your work later.[/dim]",
            title="Cancelled",
            border_style="yellow"
        ))
        sys.exit(0)
    except Exception as e:
        console.print(Panel(
            f"[red]✖ Unexpected error during enhancement:[/red]\n{str(e)}\n\n"
            "[yellow]Please check the error and try again.[/yellow]",
            title="Enhancement Error",
            border_style="red"
        ))
        sys.exit(1)

    if enhanced_prompt:
        try:
            save_enhancement(prompt, enhanced_prompt, final_style, final_model)
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Warning: Could not save to history: {e}")

        success_panel = Panel(
            f"[green]✔[/green] Your prompt has been successfully enhanced!\n"
            f"[blue]Provider:[/blue] {_provider_label(effective_provider)} | "
            f"[blue]Style:[/blue] {final_style} | [blue]Model:[/blue] {final_model}\n"
            f"[dim]Tokens generated: {len(enhanced_prompt)}[/dim]\n"
            f"[dim]Note: Response Speed/Quality depend on System's/AI-model's performance.[/dim]",
            title="Success",
            border_style="green"
        )
        console.print(success_panel)

        if diff:
            try:
                console.print("\n[bold yellow]↔️  Diff View ↔️[/bold yellow]")
                diff_result = difflib.unified_diff(
                    prompt.splitlines(keepends=True),
                    enhanced_prompt.splitlines(keepends=True),
                    fromfile='Original',
                    tofile='Enhanced',
                )
                for line in diff_result:
                    if line.startswith('+'):
                        console.print(f"[green]{line}[/green]", end="")
                    elif line.startswith('-'):
                        console.print(f"[red]{line}[/red]", end="")
                    elif line.startswith('@'):
                        console.print(f"[dim]{line}[/dim]", end="")
                    else:
                        console.print(line, end="")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Warning: Could not generate diff view: {e}")

        console.print("\n[bold magenta]✨ Enhanced Prompt ✨[/bold magenta]")
        try:
            console.print(Panel(Markdown(enhanced_prompt), 
                              title="Your Enhanced Prompt", 
                              border_style="green",
                              expand=False))
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Warning: Could not render markdown: {e}")
            console.print(Panel(enhanced_prompt, 
                              title="Your Enhanced Prompt", 
                              border_style="green",
                              expand=False))

        if output_file:
            try:
                output_file.write(enhanced_prompt)
                console.print(f"\n[green]✔[/green] Saved to [cyan]{output_file.name}[/cyan]")
            except Exception as e:
                console.print(Panel(
                    f"[red]✖ Error saving to file:[/red]\n{str(e)}\n\n"
                    f"[yellow]Please check file permissions and path.[/yellow]",
                    title="File Error",
                    border_style="red"
                ))

        if auto_copy_enabled:
            try:
                copy_to_clipboard(enhanced_prompt)
            except Exception as e:
                console.print(Panel(
                    f"[red]✖ Unexpected error during clipboard copy:[/red]\n{str(e)}\n\n"
                    f"[yellow]You can manually copy the prompt above.[/yellow]",
                    title="Clipboard Error",
                    border_style="red"
                ))
    else:
        console.print(Panel(
            "[red]✖ Failed to generate enhanced prompt.[/red]\n\n"
            "[yellow]This might happen if:[/yellow]\n"
            "• The model is not responding\n"
            "• The prompt was invalid\n"
            "• There was a network issue\n\n"
            "[bold]Try:[/bold]\n"
            "• Checking the backend status\n"
            "• Using a different model\n"
            "• Simplifying your prompt",
            title="Error",
            border_style="red"
        ))
        sys.exit(1)


def _pick_model(provider, client, config, model_name, available_models):
    """Resolve which model to use for the given provider.

    Returns the model string, or None after printing a fatal error.
    """
    if provider == "ollama":
        if model_name:
            if model_name not in available_models:
                print("")
                console = Console()
                console.print(Panel(
                    f"[red]✖ Model '{model_name}' not found.[/red]\n\n"
                    f"[bold]Available models:[/bold]\n" +
                    ("\n".join([f"• {model}" for model in available_models]) if available_models else "[yellow]No models available[/yellow]") +
                    "\n\n[bold]To install models:[/bold]\n"
                    "• Run [cyan]enhance --auto-setup[/cyan]\n"
                    "• Or manually: [cyan]ollama pull <model-name>[/cyan]",
                    title="Model Error",
                    border_style="red"
                ))
                return None
            return model_name

        preferred_models = config.get('preferred_models', OLLAMA_MODEL_NAMES)
        for model in preferred_models:
            if model in available_models:
                return model
        if available_models:
            console = Console()
            console.print(Panel(
                f"[yellow]Warning: Using '{available_models[0]}' as it's the only available model.[/yellow]\n"
                f"[dim]Configure preferred models in ~/.enhance-this/config.yaml[/dim]",
                title="Model Selection",
                border_style="yellow"
            ))
            return available_models[0]
        console = Console()
        console.print(Panel(
            "[red]✖ No models available.[/red]\n\n"
            "[bold]To resolve this:[/bold]\n"
            "1. Run [cyan]enhance --auto-setup[/cyan] (recommended)\n"
            "2. Or manually install a model: [cyan]ollama pull llama3.1:8b[/cyan]",
            title="Model Error",
            border_style="red"
        ))
        return None

    # API provider: use explicit, else remembered, else configured default.
    return resolve_api_model(config, model_name)


def run_config_wizard(console, config_path):
    """Run the interactive configuration wizard for first-time setup."""
    from .config import get_config_path
    from .providers.openai_compatible import OPENAI_COMPAT_DEFAULTS, DEFAULT_API_MODELS
    import yaml

    console.print(Panel("[bold blue]🔧 Configuration Wizard[/bold blue]\n"
                       "Let's set up enhance-this!\n"
                       "[dim]Press Ctrl+C anytime to exit.[/dim]",
                       title="Welcome", border_style="blue"))

    try:
        config_file_path = get_config_path(config_path)

        try:
            if config_file_path.exists():
                with open(config_file_path, 'r') as f:
                    current_config = yaml.safe_load(f) or {}
            else:
                current_config = {}
        except Exception:
            current_config = {}

        config = {**DEFAULT_CONFIG, **current_config}

        # Step 0: Provider selection
        console.print("\n[bold]⚙️  Backend Provider[/bold]")
        console.print("[dim]ollama = 100% local & free. api = hosted (OpenRouter/OpenAI/Groq) with your own key.[/dim]")
        provider_choices = [
            questionary.Choice(
                title="Ollama (local models running on this machine)",
                value="ollama",
                checked=config.get('provider') != 'api',
            ),
            questionary.Choice(
                title="API (bring your own key - OpenRouter, OpenAI, Groq, ...)",
                value="api",
                checked=config.get('provider') == 'api',
            ),
        ]
        provider = questionary.select(
            "Which backend do you want to use?",
            choices=provider_choices,
        ).ask()
        if provider is None:
            return
        config['provider'] = provider

        # Step 1: Ollama host (only surfaced for local provider)
        if provider == "ollama":
            console.print("\n[bold]🌐 Ollama Configuration[/bold]")
            host = questionary.text(
                "What's your Ollama host address?",
                default=config.get('ollama_host', DEFAULT_CONFIG['ollama_host'])
            ).ask()
            if host is None:
                return
            config['ollama_host'] = host
        else:
            # API provider specifics
            console.print("\n[bold]🌐 API Provider Configuration[/bold]")
            api_provider_choices = [
                questionary.Choice(title="OpenRouter", value="openrouter"),
                questionary.Choice(title="OpenAI", value="openai"),
                questionary.Choice(title="Groq", value="groq"),
                questionary.Choice(title="Together", value="together"),
                questionary.Choice(title="DeepSeek", value="deepseek"),
                questionary.Choice(title="Mistral", value="mistral"),
                questionary.Choice(title="Other (custom base URL)", value="__other__"),
            ]
            api_provider = questionary.select(
                "Which API provider?",
                choices=api_provider_choices,
                default=config.get('api_provider', 'openrouter'),
            ).ask()
            if api_provider is None:
                return
            if api_provider == "__other__":
                config['api_provider'] = "openrouter"
                base_url = questionary.text(
                    "Custom base URL (e.g. https://api.example.com/v1):",
                    default=config.get('api_base_url', 'https://openrouter.ai/api/v1')
                ).ask()
                if base_url is None:
                    return
                config['api_base_url'] = base_url
                config['api_model'] = config.get('api_model', '')
            else:
                config['api_provider'] = api_provider
                spec = OPENAI_COMPAT_DEFAULTS.get(api_provider, {})
                config['api_base_url'] = spec.get('base_url', config.get('api_base_url', 'https://openrouter.ai/api/v1'))
                config['api_model'] = config.get('api_model', '')

            console.print(f"[dim]Default model for {config['api_provider']}: "
                          f"{DEFAULT_API_MODELS.get(config['api_provider'], 'gpt-4o-mini')}[/dim]")

        # Step 2: Default Style
        console.print("\n[bold]🎨 Default Enhancement Style[/bold]")
        style = questionary.select(
            "Choose your preferred enhancement style:",
            choices=[
                'detailed', 'concise', 'creative', 'technical', 
                'json', 'bullets', 'summary', 'formal', 'casual'
            ],
            default=config.get('default_style', DEFAULT_CONFIG['default_style'])
        ).ask()
        if style is None:
            return
        config['default_style'] = style

        # Step 3: Temperature
        console.print("\n[bold]🌡️  Generation Temperature[/bold]")
        temp = questionary.text(
            "Set default temperature (0.0-2.0, lower = more focused, higher = more creative):",
            default=str(config.get('default_temperature', DEFAULT_CONFIG['default_temperature'])),
            validate=lambda x: x.replace('.', '').isdigit() and 0.0 <= float(x) <= 2.0
        ).ask()
        if temp is None:
            return
        config['default_temperature'] = float(temp)

        # Step 4: Max Tokens
        console.print("\n[bold]📏 Response Length[/bold]")
        tokens = questionary.text(
            "Set maximum tokens for responses:",
            default=str(config.get('max_tokens', DEFAULT_CONFIG['max_tokens'])),
            validate=lambda x: x.isdigit() and int(x) > 0
        ).ask()
        if tokens is None:
            return
        config['max_tokens'] = int(tokens)

        # Step 5: Auto Copy
        console.print("\n[bold]📋 Clipboard Settings[/bold]")
        auto_copy = questionary.confirm(
            "Automatically copy enhanced prompts to clipboard?",
            default=config.get('auto_copy', DEFAULT_CONFIG['auto_copy'])
        ).ask()
        if auto_copy is None:
            return
        config['auto_copy'] = auto_copy

        # Step 6: Preferred models (Ollama) / API key (API provider)
        if provider == "ollama":
            console.print("\n[bold]🤖 Preferred Models[/bold]")
            console.print("[dim]Enter your preferred models in order of preference (comma-separated)[/dim]")
            models_input = questionary.text(
                "Preferred models:",
                default=",".join(config.get('preferred_models', DEFAULT_CONFIG['preferred_models']))
            ).ask()
            if models_input is None:
                return
            config['preferred_models'] = [m.strip() for m in models_input.split(',') if m.strip()]
        else:
            console.print("\n[bold]🔑 API Key[/bold]")
            console.print("[dim]You can leave this blank and set the environment variable instead "
                          "(e.g. OPENROUTER_API_KEY). The key is stored locally in config.yaml.[/dim]")
            key = questionary.text(
                "API key (press Enter to skip):",
                default=config.get('api_key', '') or '',
            ).ask()
            if key is None:
                return
            if key.strip():
                config['api_key'] = key.strip()

            # Step 6b: API model selection
            console.print("\n[bold]🤖 Default API Model[/bold]")
            api_models = config.get('preferred_api_models') or DEFAULT_CONFIG.get('preferred_api_models', [])
            defaults = [config.get('api_model')] if config.get('api_model') else []
            choices = list(dict.fromkeys([c for c in defaults + api_models if c]))
            model_choice = questionary.select(
                "Choose a default API model (you can change it anytime with --model):",
                choices=choices + ["Other (type a model name)"],
                default=config.get('api_model') or choices[0] if choices else None,
            ).ask()
            if model_choice is None:
                return
            if model_choice == "Other (type a model name)":
                custom_model = questionary.text(
                    "Enter API model name (e.g. anthropic/claude-3.5-sonnet):"
                ).ask()
                if custom_model is None:
                    return
                config['api_model'] = custom_model.strip()
            else:
                config['api_model'] = model_choice

        # Save configuration
        config_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        if provider == "ollama":
            next_steps = (
                "• Run [cyan]enhance --auto-setup[/cyan] to download a recommended model\n"
                "• Or manually install a model: [cyan]ollama pull llama3.1:8b[/cyan]"
            )
        else:
            next_steps = (
                "• Run [cyan]enhance \"your prompt\" --provider api[/cyan] to enhance a prompt\n"
                "• Switch models anytime with [cyan]--model <name>[/cyan]\n"
                f"• Current API provider: [cyan]{config.get('api_provider')}[/cyan]"
            )

        console.print(Panel(f"[green]✅ Configuration saved successfully![/green]\n"
                           f"Location: {config_file_path}\n\n"
                           "[bold]Next steps:[/bold]\n"
                           + next_steps,
                           title="Setup Complete", border_style="green"))

    except KeyboardInterrupt:
        console.print("\n[yellow]Configuration wizard cancelled.[/yellow]")
    except Exception as e:
        console.print(Panel(f"[red]❌ Error saving configuration:[/red]\n{str(e)}",
                           title="Error", border_style="red"))


def run_template_editor(console, config):
    """Launch the visual template editor."""
    from .config import get_config_dir
    from .enhancer import PromptEnhancer
    import os
    import tempfile

    console.print(Panel("[bold magenta]🎨 Visual Template Editor[/bold magenta]\n"
                       "Create and edit custom prompt templates\n"
                       "[dim]Press Ctrl+C anytime to exit.[/dim]",
                       title="Template Editor", border_style="magenta"))

    try:
        templates_dir = get_config_dir() / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        enhancer = PromptEnhancer(config.get('enhancement_templates'))

        while True:
            console.print("\n[bold]📝 Current Templates:[/bold]")
            all_templates = list(enhancer.templates.keys())
            template_choices = [(f"{t} {'(custom)' if t not in ['detailed', 'concise', 'creative', 'technical', 'json', 'bullets', 'summary', 'formal', 'casual'] else '(built-in)'}", t) for t in all_templates]
            template_choices.append(("➕ Create new template", "create_new"))
            template_choices.append(("🚪 Exit editor", "exit"))

            selected_action = questionary.select(
                "Select a template to edit or action:",
                choices=[choice[0] for choice in template_choices]
            ).ask()

            if selected_action is None:
                break

            selected_value = None
            for choice in template_choices:
                if choice[0] == selected_action:
                    selected_value = choice[1]
                    break

            if selected_value == "exit":
                break

            if selected_value == "create_new":
                template_name = questionary.text("Enter template name:").ask()
                if template_name is None:
                    continue

                if template_name in enhancer.templates:
                    console.print("[yellow]Template already exists. Editing existing template.[/yellow]")

                default_content = enhancer.templates.get('detailed', 
                    "You are an expert prompt engineer.\n\n"
                    "Transform the user's basic prompt into a comprehensive, actionable prompt.\n\n"
                    "Original prompt: \"{user_prompt}\"\n\n"
                    "Transform this into a detailed prompt that will generate high-quality responses.")

                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
                    tmp_file.write(default_content)
                    tmp_file_path = tmp_file.name

                try:
                    editor = os.environ.get('EDITOR', 'nano')
                    os.system(f'{editor} {tmp_file_path}')

                    with open(tmp_file_path, 'r') as f:
                        edited_content = f.read()

                    if edited_content != default_content:
                        template_path = templates_dir / f"{template_name}.txt"
                        with open(template_path, 'w') as f:
                            f.write(edited_content)
                        console.print(f"[green]✅ Template '{template_name}' saved![/green]")
                    else:
                        console.print("[yellow]No changes made.[/yellow]")
                finally:
                    os.unlink(tmp_file_path)
                    enhancer = PromptEnhancer(config.get('enhancement_templates'))
            else:
                template_name = selected_value
                if template_name:
                    content = enhancer.templates.get(template_name, "")
                    console.print(f"\n[bold]Template: {template_name}[/bold]")
                    console.print(Panel(content, title="Current Content", border_style="blue"))

                    if questionary.confirm("Edit this template?").ask():
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
                            tmp_file.write(content)
                            tmp_file_path = tmp_file.name

                        try:
                            editor = os.environ.get('EDITOR', 'nano')
                            os.system(f'{editor} {tmp_file_path}')

                            with open(tmp_file_path, 'r') as f:
                                edited_content = f.read()

                            if edited_content != content:
                                if template_name in ['detailed', 'concise', 'creative', 'technical', 'json', 'bullets', 'summary', 'formal', 'casual']:
                                    new_name = questionary.text(
                                        "Built-in templates cannot be modified directly. Save as new template name:",
                                        default=f"custom_{template_name}"
                                    ).ask()
                                    if new_name:
                                        template_path = templates_dir / f"{new_name}.txt"
                                        with open(template_path, 'w') as f:
                                            f.write(edited_content)
                                        console.print(f"[green]✅ Template '{new_name}' saved![/green]")
                                else:
                                    template_path = templates_dir / f"{template_name}.txt"
                                    with open(template_path, 'w') as f:
                                        f.write(edited_content)
                                    console.print(f"[green]✅ Template '{template_name}' updated![/green]")
                            else:
                                console.print("[yellow]No changes made.[/yellow]")
                        finally:
                            os.unlink(tmp_file_path)

                        enhancer = PromptEnhancer(config.get('enhancement_templates'))

    except KeyboardInterrupt:
        console.print("\n[yellow]Template editor exited.[/yellow]")
    except Exception as e:
        console.print(Panel(f"[red]❌ Error in template editor:[/red]\n{str(e)}",
                           title="Error", border_style="red"))


# Shared streaming/display logic, used by both interactive and one-shot modes.
THINKING_MESSAGES = [
    "The AI is pondering...",
    "Analyzing the request...",
    "Consulting the digital muses...",
    "Crafting a response...",
    "The gears of thought are turning...",
    "Unraveling the query...",
    "Formulating a brilliant reply...",
    "Just a moment, weaving some magic...",
    "The model is in deep thought...",
    "Brewing a creative response...",
]


def _show_thinking(console, live_display, messages):
    live_display.update(Panel(
        f"[bold cyan]{random.choice(messages)}[/bold cyan]",
        title="[bold blue]🧠 The selected model is a Thinking one... Let it do the magic[/bold blue]",
        border_style="cyan",
        expand=True,
        padding=(1, 2),
    ))


def _stream_generate_with_live(
    client,
    final_model,
    system_prompt,
    temperature,
    max_tokens,
    console,
    *,
    spinner_name="dots",
    content_style="yellow",
):
    """Stream a model response with a rich live UI and return the full text.

    Raises ProviderConnectionError / ProviderTimeoutError / ProviderAuthError
    on transport failures so callers decide how to recover (exit vs retry).
    """
    thinking_messages = list(THINKING_MESSAGES)
    random.shuffle(thinking_messages)

    enhanced_prompt = ""
    is_thinking = False
    think_buffer = ""
    chunk_count = 0
    last_message_update_time = 0.0

    stream_generator = client.generate_stream(
        final_model, system_prompt, temperature, max_tokens
    )

    with Live(console=console, auto_refresh=True, refresh_per_second=4) as live_display:
        initial_panel = Panel(
            "[cyan]Loading model and generating response...[/cyan]\n"
            "[dim]This may take a moment for larger models.[/dim]",
            title="[bold blue]🧠 AI Generation in Progress[/bold blue]",
            border_style="cyan",
            expand=True,
            padding=(1, 2),
        )
        display_table = Table.grid(padding=1)
        display_table.add_column(width=5)
        display_table.add_column()
        display_table.add_row(Spinner(spinner_name, style="cyan"), initial_panel)
        live_display.update(display_table)

        for chunk in stream_generator:
            if is_thinking:
                think_buffer += chunk
                if time.time() - last_message_update_time > 2:
                    _show_thinking(console, live_display, thinking_messages)
                    last_message_update_time = time.time()
                if " response" in think_buffer:
                    is_thinking = False
                    think_buffer = ""
            elif " thinking" in chunk:
                is_thinking = True
                last_message_update_time = time.time()
                _show_thinking(console, live_display, thinking_messages)
            else:
                enhanced_prompt += chunk
                chunk_count += 1
                if enhanced_prompt:
                    content_preview = enhanced_prompt
                    if len(content_preview) > 2000:
                        content_preview = content_preview[:2000] + "\n... (content truncated for display)"
                    content_panel = Panel(
                        Text(content_preview, style=content_style),
                        title=f"[cyan]Streaming Response[/cyan] [dim]Using 🤖: {final_model}[/dim]",
                        border_style="green",
                        expand=True,
                        padding=(1, 2),
                    )
                    display_table = Table.grid(padding=1)
                    display_table.add_column(width=5)
                    display_table.add_column()
                    display_table.add_row(Spinner(spinner_name, style="green"), content_panel)
                    live_display.update(display_table)

        if chunk_count == 0:
            console.print("[yellow]⚠[/yellow] Warning: No response received from model.")

        completion_panel = Panel(
            "[green]✨ Enhancement complete! AI response generated successfully.[/green]",
            title="[bold green]✅ Success[/bold green]",
            border_style="green",
            expand=False,
            padding=(1, 2),
        )
        display_table = Table.grid(padding=1)
        display_table.add_column(width=5)
        display_table.add_column()
        display_table.add_row("[green]✔[/green]", completion_panel)
        live_display.update(display_table)
        time.sleep(0.8)

    return enhanced_prompt


if __name__ == '__main__':
    enhance()