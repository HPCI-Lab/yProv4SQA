"""
yprov4sqa/cli/prov_chat.py
==========================
prov-chat CLI command — follows the same Click pattern as the
existing fetch-sqa-reports, process-provenance, compare, json2graph.

After pip install -e . this is available as:
    prov-chat prov_output.json
    prov-chat prov_output.json --model qwen2.5
    prov-chat prov_output.json --provider google
    prov-chat prov_output.json --web --port 5000
"""

import os
import sys
import click


def _load_dotenv():
    """Load .env from the current working directory if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv optional — user can export vars manually


@click.command()
@click.argument('prov_path', type=click.Path(), default=None, required=False)
@click.option('--provider', default='ollama',
              type=click.Choice(['ollama', 'google'], case_sensitive=False),
              show_default=True,
              help='LLM provider: ollama (local) or google (Gemini)')
@click.option('--model',  default=None,
              help='Model name (default: llama3.2 for ollama, gemini-2.0-flash for google)')
@click.option('--api-key', default=None, envvar='GOOGLE_API_KEY',
              help='Google API key (or set GOOGLE_API_KEY in .env)')
@click.option('--ollama', default='http://localhost:11434',
              show_default=True,
              help='Ollama server URL (ignored when --provider google)')
@click.option('--web',    is_flag=True, default=False,
              help='Launch browser UI instead of terminal')
@click.option('--host',   default='127.0.0.1', show_default=True)
@click.option('--port',   default=5000, type=int, show_default=True)
def main(prov_path, provider, model, api_key, ollama, web, host, port):
    """
    Conversational agentic AI over a provenance document.

    Defaults to a local Ollama model. Use --provider google for
    fast cloud replies via the Gemini API (requires GOOGLE_API_KEY).

    \b
    Examples:
        prov-chat                             (web landing page)
        prov-chat --web                       (web landing page)
        prov-chat prov_output.json            (terminal mode)
        prov-chat prov_output.json --web      (web, skip landing)
        prov-chat prov_output.json --provider google
        prov-chat prov_output.json --web --port 5000
    """
    _load_dotenv()

    # Apply per-provider model defaults
    if model is None:
        model = 'gemini-2.0-flash' if provider.lower() == 'google' else 'llama3.2'

    # Resolve api_key: CLI flag → env var (dotenv already loaded above)
    if provider.lower() == 'google' and not api_key:
        api_key = os.environ.get('GOOGLE_API_KEY')

    from yprov4sqa.agent import ProvAgent
    from yprov4sqa.agent import loader  # import module so ROWS/REPO reflect post-load state

    # ── Web mode ───────────────────────────────────────────────────────────
    if web or prov_path is None:
        from yprov4sqa.agent.server import create_app

        agent = None
        if prov_path:
            if not os.path.exists(prov_path):
                raise click.BadParameter(f"File not found: {prov_path}",
                                         param_hint="'PROV_PATH'")
            agent = ProvAgent(prov_path, model_name=model, base_url=ollama,
                              provider=provider, api_key=api_key)

        app = create_app(agent, provider=provider, model=model,
                         api_key=api_key, ollama_url=ollama)

        if agent:
            click.echo(f"\n  Web UI → http://{host}:{port}/app\n")
        else:
            click.echo(f"\n  Web UI → http://{host}:{port}  (landing page — upload or generate a document)\n")

        app.run(host=host, port=port, debug=False)
        return

    # ── Terminal mode requires a prov_path ─────────────────────────────────
    if not os.path.exists(prov_path):
        raise click.BadParameter(f"File not found: {prov_path}",
                                 param_hint="'PROV_PATH'")

    # ── Terminal CLI ───────────────────────────────────────────────────
    try:
        from rich.console import Console
        from rich.panel   import Panel
        from rich.markdown import Markdown
        from rich.table   import Table
        console = Console()
        HAS_RICH = True
    except ImportError:
        HAS_RICH = False
        console  = None

    agent = ProvAgent(prov_path, model_name=model, base_url=ollama,
                      provider=provider, api_key=api_key)

    provider_label = 'Google Gemini' if provider.lower() == 'google' else 'Ollama'

    if HAS_RICH:
        t = Table(show_header=False, box=None, padding=(0, 1))
        t.add_row('[bold green]yProv4SQA[/] Agent', '[dim]Chat[/]')
        t.add_row('[dim]Repo[/]',
                  f'[cyan]{loader.REPO.get("name", "")}[/]')
        t.add_row('[dim]Loaded[/]',
                  f'[white]{len(loader.ROWS)} assessments[/]')
        t.add_row('[dim]Model[/]',
                  f'[white]{model}[/] [dim]({provider_label})[/]')
        console.print(Panel(
            t,
            title='[bold]Conversational Provenance Agent[/]',
            border_style='green',
        ))
        console.print(
            "[dim]Ask anything. 'reset' clears history. 'quit' exits.[/]\n"
        )
    else:
        print('='*55)
        print(f"  yProv4SQA — Chat Agent  |  {model}  ({provider_label})")
        print(f"  Repo   : {loader.REPO.get('name')}")
        print(f"  Loaded : {len(loader.ROWS)} assessments")
        print('='*55)
        print("Type question | 'reset' | 'quit'\n")

    while True:
        try:
            question = (
                console.input('\n[bold blue]You[/]: ')
                if HAS_RICH else
                input('\nYou: ')
            ).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not question:
            continue
        if question.lower() in ('quit', 'exit', 'q'):
            break
        if question.lower() == 'reset':
            agent.reset()
            if HAS_RICH:
                console.print('[dim]Conversation reset.[/]')
            else:
                print('Conversation reset.')
            continue

        try:
            if HAS_RICH:
                def _stream(token: str):
                    sys.stdout.write(token)
                    sys.stdout.flush()

                console.print('\n[bold green]Agent:[/]')
                result = agent.ask(question, on_token=_stream)
                print()  # newline after streamed content

                # Print tool calls summary below the answer
                for tc in result['tool_calls']:
                    console.print(
                        f"  [yellow]▶ {tc['tool']}[/]"
                        f"  [dim]{str(tc['input'])[:70]}[/]"
                    )
                console.print(f"[dim]  {result['steps']} tool call(s)[/]")
            else:
                print('\nAGENT: ', end='', flush=True)
                result = agent.ask(
                    question,
                    on_token=lambda t: print(t, end='', flush=True),
                )
                print()
                for tc in result['tool_calls']:
                    print(f"  [tool] {tc['tool']}({str(tc['input'])[:50]})")

        except Exception as e:
            if HAS_RICH:
                console.print(f'[red]Error:[/] {e}')
            else:
                print(f'Error: {e}')


if __name__ == '__main__':
    main()
