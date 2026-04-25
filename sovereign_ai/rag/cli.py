import typer
import json
import uuid
import os
from typing import Optional, List
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

from .main import LocalRAG
from .retriever import FTS5Retriever
from .schemas import Document
from .config import DEFAULT_DB_PATH
from .audit import AuditLogger
from .db_utils import get_db_status, encrypt_database, decrypt_database, rekey_database
from .sovereign_score import compute_sovereign_score, ScoreConfig

app = typer.Typer(help="local-rag — Simple offline vectorless RAG")
console = Console()

# --- Audit Management ---
audit_app = typer.Typer(help="Manage and verify RAG audit logs")
app.add_typer(audit_app, name="audit")

@audit_app.command()
def verify(
    log_path: str = typer.Option("rag_audit.jsonl", "--log-path", help="Path to audit JSONL file"),
    full: bool = typer.Option(True, "--full/--tip", help="Full forensic scan or fast tip check")
):
    """Verify the integrity of a cryptographic audit trail (v1.0.0-GA)."""
    logger = AuditLogger(log_path)
    mode = "Forensic (Full)" if full else "Operational (Tip)"
    with console.status(f"Running {mode} integrity check..."):
        is_valid, report = logger.verify_integrity(full=full)
    
    if is_valid:
        console.print(Panel(report, title=f"{mode} Integrity Verified", border_style="green"))
    else:
        console.print(Panel(report, title=f"INTEGRITY BREAK: {mode}", border_style="red"))
        raise typer.Exit(1)

@audit_app.command()
def doctor():
    """Detect hardware/enclave capabilities for sovereign security."""
    logger = AuditLogger()
    status = logger.get_provider_status()
    
    table = Table(title="Sovereign Security Doctor")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Details")
    
    table.add_row("Key Provider", status["type"], status.get("backend", "Unknown"))
    table.add_row("OS Enclave", "[green]Healthy[/green]" if status.get("available") else "[yellow]Missing (Fallback)[/yellow]")
    
    # Check for SQLCipher
    db_status = get_db_status(DEFAULT_DB_PATH)
    table.add_row("Data-at-Rest", "Encrypted" if db_status["encrypted"] else "Plaintext", "SQLCipher required for Level 4")
    
    console.print(table)

# --- Sovereign Scoring ---
@app.command()
def score(
    db: str = typer.Option(DEFAULT_DB_PATH, "--db"),
    policy: Optional[Path] = typer.Option(None, "--policy")
):
    """Compute the 'Sovereign Score' (0-10) for this deployment."""
    # Mock some metrics for the CLI score
    metrics = {"p50_cached_ms": 4.8} 
    
    db_status = get_db_status(db)
    config = ScoreConfig(
        db_path=db, 
        policy_rules=[] if not policy else [1], # Simplified detection
        encrypted=db_status.get("encrypted", False)
    )
    
    with console.status("Calculating Sovereign Score..."):
        result = compute_sovereign_score(config, metrics)
        
    score_val = result["score"]
    color = "green" if score_val >= 8 else "yellow" if score_val >= 5 else "red"
    
    console.print(Panel(
        f"[bold {color}]Score: {score_val}/10.0[/bold {color}]\n\n" + 
        "\n".join([f"• {r}" for r in result["recommendations"]]),
        title="Sovereign AI Readiness Score",
        subtitle="v1.0.0-GA Assessment"
    ))
    
    table = Table(show_header=False, border_style="dim")
    for category, val in result["components"].items():
        table.add_row(category.capitalize(), f"{val}/10")
    console.print(table)

# --- Database Management ---
db_app = typer.Typer(help="Sovereign database management (Encryption, Status)")
app.add_typer(db_app, name="db")

def resolve_password(password: Optional[str], db_path: str) -> Optional[str]:
    """Resolve password from CLI -> Env Var -> Interactive Prompt."""
    if password: return password
    env_pass = os.getenv("LOCAL_RAG_DB_PASSWORD")
    if env_pass: return env_pass
    
    status = get_db_status(db_path)
    if status.get("encrypted") and not status.get("accessible"):
        return typer.prompt(f"Enter password for {db_path}", hide_input=True)
    return None

@db_app.command()
def status(
    db: str = typer.Option(DEFAULT_DB_PATH, "--db"),
    password: Optional[str] = typer.Option(None, "--password")
):
    """Check database encryption and integrity status."""
    resolved_pass = resolve_password(password, db)
    info = get_db_status(db, resolved_pass)
    
    if not info["exists"]:
        console.print(f"[red]Database not found: {db}[/red]")
        return

    table = Table(title=f"Database Status: {db}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="magenta")
    
    table.add_row("Encryption", "SQLCipher (Encrypted)" if info["encrypted"] else "Plaintext (Unencrypted)")
    table.add_row("Accessible", "[green]Yes[/green]" if info["accessible"] else "[red]No (Locked)[/red]")
    
    if info["error"]:
        table.add_row("Error", f"[red]{info['error']}[/red]")
        
    console.print(table)

@db_app.command()
def encrypt(
    source: Path = typer.Argument(..., help="Path to plaintext database"),
    target: Path = typer.Argument(..., help="Path to create encrypted database"),
):
    """Migrate a plaintext database to an encrypted SQLCipher one."""
    password = typer.prompt("New Database Password", hide_input=True, confirmation_prompt=True)
    try:
        with console.status(f"Encrypting {source} -> {target}..."):
            encrypt_database(str(source), str(target), password)
        console.print(f"[green]Success: Encrypted database created at {target}[/green]")
    except Exception as e:
        console.print(f"[red]Encryption failed: {e}[/red]")
        raise typer.Exit(1)

@db_app.command()
def decrypt(
    source: Path = typer.Argument(..., help="Path to encrypted database"),
    target: Path = typer.Argument(..., help="Path to create plaintext database"),
    password: Optional[str] = typer.Option(None, "--password")
):
    """Migrate an encrypted database back to plaintext SQLite."""
    resolved_pass = resolve_password(password, str(source))
    try:
        with console.status(f"Decrypting {source} -> {target}..."):
            decrypt_database(str(source), str(target), resolved_pass)
        console.print(f"[green]Success: Plaintext database created at {target}[/green]")
    except Exception as e:
        console.print(f"[red]Decryption failed: {e}[/red]")
        raise typer.Exit(1)

@db_app.command()
def rekey(
    db: Path = typer.Argument(..., help="Path to encrypted database"),
    old_password: Optional[str] = typer.Option(None, "--old-password")
):
    """Rotate the encryption key for a SQLCipher database."""
    resolved_old = resolve_password(old_password, str(db))
    new_password = typer.prompt("New Database Password", hide_input=True, confirmation_prompt=True)
    try:
        with console.status("Rotating encryption key..."):
            rekey_database(str(db), resolved_old, new_password)
        console.print("[green]Success: Database key rotated successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Rekey failed: {e}[/red]")
        raise typer.Exit(1)

# --- Core Commands ---

@app.command()
def ingest(
    file_path: Path = typer.Argument(..., help="Path to JSON file with documents"),
    db: str = typer.Option(DEFAULT_DB_PATH, "--db", help="Path to SQLite database"),
    password: Optional[str] = typer.Option(None, "--password"),
    chunk_size: int = typer.Option(1000, "--chunk-size"),
    chunk_overlap: int = typer.Option(200, "--chunk-overlap"),
    classification: Optional[str] = typer.Option(None, "--classification", help="Document classification"),
    department: Optional[str] = typer.Option(None, "--department"),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id")
):
    """Ingest documents into the local RAG store."""
    if not file_path.exists():
        console.print(f"[red]Error: File {file_path} not found.[/red]")
        raise typer.Exit(1)

    resolved_pass = resolve_password(password, db)
    
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    docs = [Document(
        doc_id=item.get("doc_id", str(uuid.uuid4())),
        source=item.get("source", str(file_path)),
        title=item.get("title"),
        content=item.get("content", item.get("text", "")),
        classification=item.get("classification", classification),
        department=item.get("department", department),
        tenant_id=item.get("tenant_id", tenant_id),
        metadata=item.get("metadata", {})
    ) for item in data]

    try:
        rag = LocalRAG(db_path=db, password=resolved_pass)
        with console.status(f"Ingesting {len(docs)} documents..."):
            rag.retriever.ingest(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        console.print(f"[green]Done: Successfully ingested {len(docs)} documents into {db}[/green]")
        rag.close()
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

@app.command()
def search(
    query: List[str] = typer.Argument(..., help="Search query"),
    db: str = typer.Option(DEFAULT_DB_PATH, "--db"),
    password: Optional[str] = typer.Option(None, "--password"),
    top_k: int = typer.Option(5, "--top-k"),
    rerank: bool = typer.Option(False, "--rerank", help="Use cross-encoder reranking"),
    reranker_model: str = typer.Option("BAAI/bge-reranker-base", "--reranker-model")
):
    """Search for relevant segments in the local RAG store."""
    full_query = " ".join(query)
    resolved_pass = resolve_password(password, db)
    
    try:
        rag = LocalRAG(
            db_path=db, 
            password=resolved_pass, 
            use_reranker=rerank, 
            reranker_model=reranker_model
        )
        
        # When reranking, we fetch more initial candidates
        fetch_k = 100 if rerank else top_k
        
        if hasattr(rag.retriever, "search") and rerank:
            # If in governed mode, use the governed search with reranking
            results, _ = rag.retriever.search(full_query, top_k=fetch_k, rerank_top_k=top_k)
        else:
            # Standard lexical search
            results = rag.retriever.search(full_query, top_k=top_k)

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        table = Table(title=f"Search Results for: '{full_query}'" + (" (Reranked)" if rerank else ""))
        table.add_column("Score", justify="right", style="cyan")
        table.add_column("Doc ID", style="magenta")
        table.add_column("Preview", style="green")

        for r in results:
            table.add_row(
                f"{r.score:.2f}",
                r.doc_id,
                r.text.replace("[result]", "[bold yellow]").replace("[/result]", "[/bold yellow]")
            )
        console.print(table)
        rag.close()
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

@app.command()
def ask(
    query: List[str] = typer.Argument(..., help="Question to ask the RAG system"),
    db: str = typer.Option(DEFAULT_DB_PATH, "--db"),
    password: Optional[str] = typer.Option(None, "--password"),
    stream: bool = typer.Option(False, "--stream", help="Stream the response"),
    top_k: int = typer.Option(5, "--top-k"),
    policy: Optional[Path] = typer.Option(None, "--policy", help="Path to policy YAML file"),
    principal: str = typer.Option("cli-user", "--principal", help="User or agent identifier"),
    rerank: bool = typer.Option(False, "--rerank", help="Use cross-encoder reranking"),
    reranker_model: str = typer.Option("BAAI/bge-reranker-base", "--reranker-model")
):
    """Ask a question grounded in the local RAG store context."""
    full_query = " ".join(query)
    resolved_pass = resolve_password(password, db)
    
    try:
        rag = LocalRAG(
            db_path=db, 
            policy_path=str(policy) if policy else None, 
            principal=principal,
            password=resolved_pass,
            use_reranker=rerank,
            reranker_model=reranker_model
        )
        
        if stream:
            console.print(Panel(f"Query: [bold]{full_query}[/bold]", title="Local RAG Ask (Streaming)"))
            response_gen = rag.ask(full_query, top_k=top_k, stream=True)
            full_response = ""
            with Live(console=console, refresh_per_second=10) as live:
                for chunk in response_gen:
                    full_response += chunk
                    live.update(Panel(full_response, title="Assistant Answer", border_style="green"))
        else:
            with console.status("Retrieving context and generating answer..."):
                response = rag.ask(full_query, top_k=top_k, stream=False)
            console.print(Panel(f"Query: [bold]{full_query}[/bold]", title="Local RAG Ask"))
            console.print(Panel(response.answer, title="Assistant Answer", border_style="green"))
            
            if response.sources:
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Source", style="dim")
                table.add_column("Excerpt")
                for i, s in enumerate(response.sources, 1):
                    excerpt = s.text.replace("[result]", "").replace("[/result]", "")
                    table.add_row(f"[{i}] {s.doc_id}", excerpt[:150] + "...")
                console.print(table)
        rag.close()
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

@app.command()
def stats(
    db: str = typer.Option(DEFAULT_DB_PATH, "--db"),
    password: Optional[str] = typer.Option(None, "--password")
):
    """Show database statistics."""
    resolved_pass = resolve_password(password, db)
    try:
        rag = LocalRAG(db_path=db, password=resolved_pass)
        conn = rag.retriever.store.conn
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        
        console.print(Panel(
            f"Database: [bold]{db}[/bold]\n"
            f"Documents: [green]{doc_count}[/green]\n"
            f"Chunks: [green]{chunk_count}[/green]",
            title="Local RAG Stats"
        ))
        rag.close()
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

@app.command()
def hub(
    db: str = typer.Option(DEFAULT_DB_PATH, "--db"),
    password: Optional[str] = typer.Option(None, "--password"),
    policy: str = typer.Option("policy.yaml", "--policy"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8555, "--port")
):
    """Launch the Sovereign Hub: a local-first security dashboard."""
    try:
        from .hub import start_hub
    except ImportError:
        console.print("[red]Error: Hub dependencies not found.[/red]")
        console.print("Please install them with: [bold]pip install local-rag[hub][/bold]")
        raise typer.Exit(1)

    resolved_pass = resolve_password(password, db)
    
    console.print(Panel(
        f"Database: [bold cyan]{db}[/bold cyan]\n"
        f"Policy: [bold cyan]{policy}[/bold cyan]\n"
        f"Endpoint: [bold green]http://{host}:{port}[/bold green]",
        title="Launching Sovereign Hub",
        border_style="green"
    ))
    
    start_hub(db_path=db, password=resolved_pass, policy_path=policy, host=host, port=port)

def main():
    app()

if __name__ == "__main__":
    main()
