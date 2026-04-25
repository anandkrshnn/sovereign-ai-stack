import asyncio
import click
import uuid
import sys
from .pipeline import SovereignPipeline, Config
from .rag.schemas import Document

@click.group()
def main():
    """Sovereign AI Stack CLI - Local, Governed, Auditable AI."""
    pass

@main.command()
def version():
    """Display the version of the Sovereign AI Stack."""
    from . import __version__
    click.echo(f"Sovereign AI Stack v{__version__}")

@main.command()
@click.argument("query")
@click.option("--principal", default="anonymous", help="Identity principal for ABAC.")
@click.option("--tenant", default="default", help="Tenant ID for isolation.")
@click.option("--verify", is_flag=True, help="Enable grounding verification.")
def ask(query, principal, tenant, verify):
    """Query the sovereign vault."""
    config = Config(
        principal=principal,
        tenant_id=tenant,
        enable_verification=verify
    )
    pipeline = SovereignPipeline(config)
    
    async def run():
        res = await pipeline.ask(query)
        click.echo(f"\n[Sovereign Response]\n{res.answer}")
        if "verification" in res.metadata:
            click.echo(f"\n[Verification] Score: {res.metadata['verification'].get('overall_score', 0):.2f}")
        await pipeline.close()

    asyncio.run(run())

@main.command()
@click.argument("path")
@click.option("--tenant", default="default", help="Tenant ID for isolation.")
def ingest(path, tenant):
    """Ingest a text file into the sovereign vault."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    doc = Document(
        doc_id=str(uuid.uuid4()),
        source=path,
        content=content,
        tenant_id=tenant
    )
    
    config = Config(tenant_id=tenant)
    pipeline = SovereignPipeline(config)
    
    async def run():
        await pipeline.ingest([doc])
        click.echo(f"Ingested {path} into tenant {tenant}")
        await pipeline.close()

    asyncio.run(run())

@main.group()
def audit():
    """Manage the forensic audit chain."""
    pass

@audit.command()
@click.option("--tenant", default="default", help="Tenant ID to verify.")
@click.option("--base-dir", default="data", help="Base directory for logs.")
def verify(tenant, base_dir):
    """Verify the integrity of the forensic audit chain."""
    from .common.audit import SovereignAuditLogger
    logger = SovereignAuditLogger(base_dir, tenant)
    if logger.verify_integrity():
        click.echo(f"Audit chain for tenant '{tenant}' is VALID (100% Integrity).")
    else:
        click.echo(f"CRITICAL: Audit chain for tenant '{tenant}' is CORRUPTED or TAMPERED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
