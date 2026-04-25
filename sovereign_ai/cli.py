import asyncio
import click
from .pipeline import SovereignPipeline, Config
from .rag.schemas import Document

@click.group()
def main():
    """🛡️ Sovereign AI Stack CLI - Local, Governed, Auditable AI."""
    pass

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
    
    docs = [Document(text=content, metadata={"source": path})]
    config = Config(tenant_id=tenant)
    pipeline = SovereignPipeline(config)
    
    async def run():
        await pipeline.ingest(docs)
        click.echo(f"✅ Ingested {path} into tenant {tenant}")
        await pipeline.close()

    asyncio.run(run())

if __name__ == "__main__":
    main()
