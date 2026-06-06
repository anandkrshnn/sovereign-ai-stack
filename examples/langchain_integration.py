import asyncio
from rich.console import Console
from rich.panel import Panel

# This is an example, assuming user has langchain-openai installed
try:
    from langchain_openai import ChatOpenAI
    from sovereign_ai.langchain_guard import SovereignLangChainGuard
except ImportError:
    print("Please install langchain, langchain-core, and langchain-openai to run this example.")
    print("pip install langchain langchain-openai")
    exit(1)

console = Console()

async def run_example():
    console.print(Panel("[bold green]Sovereign AI Stack + LangChain Ecosystem Example[/bold green]\n"
                        "Demonstrates wrapping a LangChain ChatModel in the Sovereign Verify-First Airlock."))
    
    # 1. Initialize a standard LangChain LLM
    # (Requires OPENAI_API_KEY environment variable)
    try:
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
    except Exception as e:
        console.print(f"[bold red]Failed to initialize ChatOpenAI: {e}[/bold red]")
        console.print("Make sure you have set the OPENAI_API_KEY environment variable.")
        return

    # 2. Wrap it with the Sovereign Guard
    # We set a high threshold and fail_closed=True (default) to enforce strict gating
    guard = SovereignLangChainGuard(llm=llm, nli_threshold=0.85)
    
    # 3. Create a LangChain LCEL pipeline
    # We can use the guard just like any other Runnable
    # In a real app, this could be: prompt | guard | StrOutputParser()
    chain = guard
    
    query = "What is the capital of France?"
    context = "Paris is the capital of France, known for its cafe culture and the Eiffel Tower."
    
    console.print(f"\n[cyan]Executing query:[/cyan] {query}")
    console.print(f"[cyan]With context:[/cyan] {context}\n")
    
    try:
        # ainvoke expects a dict with 'input' and optionally 'context'
        result = await chain.ainvoke({"input": query, "context": context})
        
        console.print(Panel(
            f"[bold green]Generation Passed Verification![/bold green]\n\n"
            f"[bold]Output:[/bold] {result['output']}\n"
            f"[bold]NLI Score:[/bold] {result['verification_score']:.2f}\n",
            title="Sovereign Airlock Results",
            border_style="green"
        ))
    except ValueError as ve:
        console.print(Panel(
            f"[bold red]Generation Blocked by Airlock[/bold red]\n\n{str(ve)}",
            title="Sovereign Verification Failed",
            border_style="red"
        ))

if __name__ == "__main__":
    asyncio.run(run_example())
