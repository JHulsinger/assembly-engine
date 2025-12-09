import sys
import os
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.spinner import Spinner
from rich.live import Live
from rich.layout import Layout
from rich import print as rprint

from indexer import Indexer
from retriever import IntersectionEngine
from assembler import Assembler

console = Console()

class VerificationLoop:
    """
    Component: Quality Assurance
    Task ID: VERIFIER_01
    """
    def compile_and_fix(self, source_code: str, filename: str) -> bool:
        console.print(f"[bold cyan]Verifier[/]: Writing code to [yellow]{filename}[/yellow]...")
        with open(filename, "w") as f:
            f.write(source_code)
            
        # Check strict syntax using python -m py_compile
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", filename],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                console.print(f"[bold red]Syntax Error:[/]\n{result.stderr}")
                return False
                
            console.print("[bold green]Syntax Check Passed.[/]")
            return True
        except Exception as e:
            console.print(f"[bold red]Execution failed:[/] {e}")
            return False

def setup_components():
    with console.status("[bold green]Initializing Assembly Engine...[/]"):
        try:
            indexer = Indexer()
            retriever = IntersectionEngine()
            assembler = Assembler()
            return indexer, retriever, assembler
        except Exception as e:
            console.print(f"[bold red]Initialization Failed:[/] {e}")
            return None, None, None

def index_files(indexer):
    with console.status("[bold blue]Indexing Workspace...[/]"):
        files_indexed = 0
        for root, _, files in os.walk("."):
            if "venv" in root or "__pycache__" in root: continue
            for file in files:
                if file.endswith(".py") and file not in ["test_dummy.py"]: 
                    path = os.path.join(root, file)
                    try:
                        indexer.parse_file(path)
                        files_indexed += 1
                    except Exception as e:
                        console.print(f"[red]Failed to index {path}: {e}[/]")
        
        indexer.export_index()
    console.print(f"[dim]Indexed {files_indexed} files.[/]")

def main():
    # Header
    console.print(Panel.fit(
        "[bold cyan]Assembly Engine Compiler[/]\n[dim]v1.0.0 - Interactive Mode[/]",
        border_style="cyan"
    ))
    
    # Setup
    indexer, retriever, assembler = setup_components()
    if not indexer: return

    # Index
    index_files(indexer)
    # Reload retriever
    retriever._load_index()

    # REPL Loop
    while True:
        console.print("") # spacing
        query = Prompt.ask("[bold green]>[/]")
        
        if query.lower() in ["exit", "quit", "q"]:
            console.print("[yellow]Goodbye![/]")
            break
            
        if not query.strip():
            continue

        # Retrieval
        with console.status("[bold cyan]Retrieving context...[/]"):
            results = retriever.search(query)
        
        context_count = len(results) if results else 0
        console.print(f"[dim]Retrieved {context_count} relevant chunks.[/]")
        
        # Assembly
        retrieved_context = results if results else []
        
        with console.status("[bold magenta]Assembling code (Thinking)...[/]"):
            output_obj = assembler.generate_glue_code(retrieved_context, query)
        
        # Show Reasoning
        console.print(Panel(
            output_obj.reasoning,
            title="[bold magenta]Reasoning[/]",
            border_style="magenta",
            expand=False
        ))

        # Show Code
        syntax = Syntax(output_obj.code, "python", theme="monokai", line_numbers=True)
        console.print(Panel(
            syntax,
            title=f"[bold green]Generated: {output_obj.filename}[/]",
            border_style="green",
            expand=False
        ))
        
        # Verification / Execution
        if Confirm.ask("Do you want to save and verify this code?"):
            console.print("")
            verifier = VerificationLoop()
            success = verifier.compile_and_fix(output_obj.code, output_obj.filename)
            
            if success and Confirm.ask(f"Run [yellow]{output_obj.filename}[/] now?"):
                 subprocess.run([sys.executable, output_obj.filename])

if __name__ == "__main__":
    main()
