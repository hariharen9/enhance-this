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

from .config import load_config, create_default_config_if_not_exists
from .ollama_client import OllamaClient
from .enhancer import PromptEnhancer
from .clipboard import copy_to_clipboard
from .history import save_enhancement, load_history

@click.command()
@click.argument('prompt', required=False)
@click.option('-m', '--model', 'model_name', help='Ollama model to use (auto-selects optimal if not specified)')
@click.option('-t', '--temperature', type=click.FloatRange(0.0, 2.0), help='Temperature for generation (0.0-2.0)')
@click.option('-l', '--length', 'max_tokens', type=int, help='Max tokens for enhancement')
@click.option('-c', '--config', 'config_path', type=click.Path(), help='Configuration file path')
@click.option('-v', '--verbose', is_flag=True, help='Enable verbose output')
@click.option('-n', '--no-copy', is_flag=True, help="Don't copy to clipboard")
@click.option('-o', '--output', 'output_file', type=click.File('w'), help='Save enhanced prompt to file')
@click.option('-s', '--style', type=click.Choice(['detailed', 'concise', 'creative', 'technical', 'json', 'bullets', 'summary', 'formal', 'casual']), help='Enhancement style')
@click.option('--diff', is_flag=True, help='Show a diff between the original and enhanced prompt')
@click.option('--list-models', is_flag=True, help='List available Ollama models')
@click.option('--download-model', 'download_model_name', help='Download specific model from Ollama')
@click.option('--auto-setup', is_flag=True, help='Automatically setup Ollama with optimal model')
@click.option('--history', 'show_history', is_flag=True, help='Show enhancement history.')
@click.option('--interactive', 'is_interactive', is_flag=True, help='Start an interactive enhancement session.')
@click.option('--preload-model', is_flag=True, help='Preload a model to keep it in memory for faster responses.')
@click.version_option()
@click.help_option('-h', '--help')
def enhance(prompt, model_name, temperature, max_tokens, config_path, verbose, no_copy, output_file, style, diff, list_models, download_model_name, auto_setup, show_history, is_interactive, preload_model):
    """
    Enhances a simple prompt using Ollama AI models, displays the enhanced version,
    and automatically copies it to the clipboard.
    """
    console = Console()
    config = load_config(config_path)
    client = OllamaClient(host=config['ollama_host'], timeout=config['timeout'])

    # Custom loading messages for better UX
    loading_messages = [
        "Initializing enhancement engine...",
        "Connecting to local AI model...",
        "Preparing prompt transformation...",
        "Loading language patterns...",
        "Setting up creative algorithms...",
        "Calibrating response parameters...",
        "Warming up neural pathways...",
        "Optimizing for maximum creativity...",
    ]

    if preload_model:
        available_models = client.list_models()
        if not available_models:
            console.print("[red]✖[/red] No models available to preload. Please run [bold]`enhance --auto-setup`[/bold] first.")
            sys.exit(1)

        preferred_models = config.get('preferred_models', ["llama3.1:8b", "llama3", "mistral"])
        model_to_preload = None
        for model in preferred_models:
            if model in available_models:
                model_to_preload = model
                break
        
        if not model_to_preload:
            model_to_preload = available_models[0]

        # Enhanced preloading with visual feedback
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Preloading model '{model_to_preload}'...", total=None)
            client.preload_model(model_to_preload)
            progress.update(task, description=f"[green]✔ Model '{model_to_preload}' preloaded successfully!")
            time.sleep(1)  # Brief pause for visual feedback
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
            # Enhanced history display
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
        # Enhanced welcome message
        welcome_panel = Panel(
            "[bold green]Welcome to Interactive Mode![/bold green]\n"
            "Enhance your prompts in real-time with AI assistance.\n"
            "[dim]Type 'quit' or 'exit' to end the session.[/dim]",
            title="✨ Enhance This - Interactive Mode",
            border_style="bright_blue"
        )
        console.print(welcome_panel)

        enhancer = PromptEnhancer(config.get('enhancement_templates'))
        available_styles = list(enhancer.templates.keys())
        
        if not client.is_running():
            console.print(Panel("[red]✖ Ollama service is not running or is unreachable.[/red]\n"
                              "[yellow]Please start Ollama and try again.[/yellow]", 
                              title="Connection Error", border_style="red"))
            sys.exit(1)

        available_models = client.list_models()
        if not available_models:
            console.print(Panel("[red]✖ No models available.[/red]\n"
                              "[yellow]Please run [bold]`enhance --auto-setup`[/bold] first.[/yellow]", 
                              title="Model Error", border_style="red"))
            sys.exit(1)

        if model_name and model_name not in available_models:
            console.print(Panel(f"[red]✖ Model '{model_name}' not found.[/red]", 
                              title="Model Error", border_style="red"))
            sys.exit(1)
        
        final_model = model_name or config.get('preferred_models', ["llama3.1:8b", "llama3", "mistral"])[0]

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
                
                # Enhanced loading experience
                enhanced_prompt = ""
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("[cyan]Enhancing your prompt...", total=None)
                    
                    # Simulate dynamic messages
                    for i, message in enumerate(loading_messages[:5]):
                        progress.update(task, description=f"[cyan]{message}[/cyan]")
                        time.sleep(0.3)  # Brief pause for visual effect
                    
                    # Actual enhancement
                    for chunk in client.generate_stream(final_model, system_prompt, 0.7, 2000):
                        enhanced_prompt += chunk
                        # Update with a more specific message as enhancement progresses
                        if len(enhanced_prompt) > 50:
                            progress.update(task, description="[cyan]Refining the output...[/cyan]")
                        elif len(enhanced_prompt) > 10:
                            progress.update(task, description="[cyan]Generating content...[/cyan]")
                    
                    progress.update(task, description="[green]✔ Enhancement complete![/green]")
                    time.sleep(0.5)  # Brief pause for visual feedback
                
                # Enhanced prompt display
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
                    copy_to_clipboard(enhanced_prompt)
                    console.print("[green]✔ Copied to clipboard.[/green]")
                elif action == 'q':
                    break
                else:
                    console.print("[yellow]Invalid action.[/yellow]")

            except (KeyboardInterrupt, EOFError):
                break

        console.print(Panel("[bold green]Exiting interactive mode. Goodbye![/bold green] 👋", 
                          title="Session Ended", border_style="green"))
        return

    create_default_config_if_not_exists()
    
    if not client.is_running():
        console.print(Panel("[red]✖ Ollama service is not running or is unreachable.[/red]\n"
                          "[yellow]Please start Ollama and try again.[/yellow]", 
                          title="Connection Error", border_style="red"))
        sys.exit(1)

    if list_models:
        models = client.list_models()
        if models:
            models_table = Table(title="Available Ollama Models", border_style="green")
            models_table.add_column("Model Name", style="cyan")
            for model in models:
                models_table.add_row(model)
            console.print(models_table)
        else:
            console.print(Panel("[yellow]No Ollama models found.[/yellow]", 
                              title="Models", border_style="yellow"))
        return

    if download_model_name:
        console.print(f"[bold blue]📥 Starting download for '{download_model_name}'...[/bold blue]")
        client.download_model(download_model_name)
        return
        
    available_models = client.list_models()

    if auto_setup or not available_models:
        if not available_models:
            console.print(Panel("[yellow]No models found. Starting auto-setup.[/yellow]", 
                              title="Setup", border_style="yellow"))
        else:
            console.print("[bold blue]Starting auto-setup...[/bold blue]")
        
        recommended_models = ["llama3.1:8b", "llama3", "mistral"]
        for model_to_try in recommended_models:
            if model_to_try not in available_models:
                console.print(f"[bold blue]📥 Downloading recommended model:[/bold blue] [cyan]{model_to_try}[/cyan]")
                if client.download_model(model_to_try):
                    available_models.append(model_to_try)
                    break 
            else:
                console.print(f"[green]✔[/green] Recommended model '[cyan]{model_to_try}[/cyan]' is already available.")
                break
        else:
            console.print(Panel("[red]✖ Auto-setup failed. Could not download a recommended model.[/red]", 
                              title="Setup Error", border_style="red"))
            sys.exit(1)

        if auto_setup:
             return

    if not prompt:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()

    if model_name:
        if model_name not in available_models:
            console.print(Panel(f"[red]✖ Model '{model_name}' not found.[/red]\n"
                              f"[yellow]Available models:[/yellow]\n" +
                              "\n".join([f"- {model}" for model in available_models]), 
                              title="Model Error", border_style="red"))
            sys.exit(1)
        final_model = model_name
    else:

        preferred_models = config.get('preferred_models', ["llama3.1:8b", "llama3", "mistral"])
        final_model = None
        for model in preferred_models:
            if model in available_models:
                final_model = model
                break
        
        if not final_model:
            if available_models:
                final_model = available_models[0]
            else:
                console.print(Panel("[red]✖ No models available.[/red]\n"
                                  "[yellow]Please download a model first, e.g.:[/yellow]\n"
                                  "[dim]`enhance --download-model llama3.1:8b` or run `enhance --auto-setup`[/dim]", 
                                  title="Model Error", border_style="red"))
                sys.exit(1)

        if verbose:
            console.print(f"[bold blue]No model specified.[/bold blue] Using best available model: [cyan]{final_model}[/cyan]")

    final_style = style or config.get('default_style', 'detailed')
    final_temperature = temperature if temperature is not None else config.get('default_temperature', 0.7)
    final_max_tokens = max_tokens or config.get('max_tokens', 2000)
    auto_copy_enabled = not no_copy and config.get('auto_copy', True)

    enhancer = PromptEnhancer(config.get('enhancement_templates'))

    system_prompt = enhancer.enhance(prompt, final_style)

    if verbose:
        console.print("\n[bold blue]🔧 System Prompt:[/bold blue]")
        console.print(Panel(system_prompt, title="System Prompt", border_style="dim"))

    enhanced_prompt = ""
    
    # Enhanced loading experience with dynamic messages
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Loading model and enhancing prompt...[/cyan]", total=None)
        
        # Show dynamic loading messages
        for i, message in enumerate(loading_messages):
            progress.update(task, description=f"[cyan]{message}[/cyan]")
            time.sleep(0.2)  # Brief pause for visual effect
            
            # Break early if we have a long list of messages
            if i >= len(loading_messages) - 2:
                break
        
        try:
            stream_generator = client.generate_stream(final_model, system_prompt, final_temperature, final_max_tokens)

            # Update message as we start generating
            progress.update(task, description="[cyan]Generating enhanced prompt...[/cyan]")

            # Collect the output
            for chunk in stream_generator:
                enhanced_prompt += chunk
                # Update message based on progress
                if len(enhanced_prompt) > 100:
                    progress.update(task, description="[cyan]Polishing the output...[/cyan]")
                elif len(enhanced_prompt) > 20:
                    progress.update(task, description="[cyan]Building response...[/cyan]")
            
            # Completion message
            progress.update(task, description="[green]✔ Enhancement complete![/green]")
            time.sleep(0.3)  # Brief pause for visual feedback

        except Exception as e:
            progress.update(task, description=f"[red]✖ Error during enhancement: {e}[/red]")
            time.sleep(1)
            sys.exit(1)

    if enhanced_prompt:
        save_enhancement(prompt, enhanced_prompt, final_style, final_model)
        
        # Enhanced success message
        success_panel = Panel(
            f"[green]✔[/green] Your prompt has been successfully enhanced!\n"
            f"[blue]Style:[/blue] {final_style} | [blue]Model:[/blue] {final_model}",
            title="Success",
            border_style="green"
        )
        console.print(success_panel)
        
        if diff:
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

        # Enhanced prompt display
        console.print("\n[bold magenta]✨ Enhanced Prompt ✨[/bold magenta]")
        console.print(Panel(Markdown(enhanced_prompt), 
                          title="Your Enhanced Prompt", 
                          border_style="green",
                          expand=False))

        if output_file:
            output_file.write(enhanced_prompt)
            console.print(f"\n[green]✔[/green] Saved to [cyan]{output_file.name}[/cyan]")

        if auto_copy_enabled:
            copy_to_clipboard(enhanced_prompt)
            console.print("[green]✔ Enhanced prompt copied to clipboard.[/green]")
    else:
        console.print(Panel("[red]✖ Failed to generate enhanced prompt.[/red]", 
                          title="Error", border_style="red"))
        sys.exit(1)

if __name__ == '__main__':
    enhance()