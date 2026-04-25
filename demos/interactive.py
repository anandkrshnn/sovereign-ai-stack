import asyncio
import os
import sys
import shutil
from local_rag import RAGPipeline, Config

# Ensure we can find the package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def interactive_demo():
    # Force clean UI
    if os.name == 'nt': os.system('cls')
    else: os.system('clear')

    print("\n" + "="*60)
    print("[SOVEREIGN LOCAL RAG] INTERACTIVE DEMO (v1.0.0-GA)")
    print("="*60)
    
    # Get the directory of the current script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Select Tenant
    print("\n[Step 1] Select Tenant Silo:")
    print("1. Healthcare (clinic_a)")
    print("2. Finance (acme_corp)")
    print("3. Engineering (eng_team)")
    
    try:
        choice = input("\nSelect demo environment [1-3]: ")
    except EOFError: return

    if choice == "1":
        db = os.path.join(base_dir, "healthcare", "clinic_a.db")
        policy = os.path.join(base_dir, "healthcare", "policy.yaml")
        tenant = "clinic_a"
        default_roles = ["doctor"]
        demo_name = "Healthcare"
    elif choice == "2":
        db = os.path.join(base_dir, "finance", "finance.db")
        policy = os.path.join(base_dir, "finance", "policy.yaml")
        tenant = "acme_corp"
        default_roles = ["cfo"]
        demo_name = "Finance"
    else:
        db = os.path.join(base_dir, "engineering", "eng.db")
        policy = os.path.join(base_dir, "engineering", "policy.yaml")
        tenant = "eng_team"
        default_roles = ["admin"]
        demo_name = "Engineering"

    # 2. Select Identity (Principal)
    print(f"\n[Step 2] Identity Configuration ({demo_name}):")
    try:
        roles_input = input(f"Enter roles [default: {','.join(default_roles)}]: ")
        roles = roles_input.split(",") if roles_input else default_roles
        
        class_input = input("Enter classifications [default: PHI,confidential,internal,public]: ")
        classifications = class_input.split(",") if class_input else ["PHI", "confidential", "internal", "public"]
    except EOFError: return

    # 3. Initialize Pipeline
    print(f"\n[Step 3] Initializing Sovereign Airlock for {tenant}...")
    cfg = Config(
        db_path=db,
        policy_path=policy,
        tenant_id=tenant,
        roles=roles,
        classifications=classifications,
        use_reranker=False 
    )
    pipe = RAGPipeline(cfg)

    print("\n[READY] Type your query (or 'exit' to quit)")
    print("-" * 60)

    while True:
        try:
            query = input("\n[INPUT] Query: ")
            if not query: continue
            if query.lower() == 'exit': break
            
            intent = input("[INPUT] Intent [default: general]: ") or "general"
        except (EOFError, KeyboardInterrupt):
            break

        print("\n[PROCESS] Running Sovereign Pipeline...")
        print("  |-- [Search] Querying siloed FTS5 + LanceDB...")
        
        res = await pipe.ask(query, intent=intent)
        
        # Check if the answer itself mentions denial
        is_denied = "[Sovereign Access Denied]" in res.answer or "[Sovereign Privacy Guardrail]" in res.answer
        
        print(f"  |-- [Airlock] Decision: {'DENIED' if is_denied else 'AUTHORIZED'}")
        
        if res.sources:
            print(f"  |-- [Sources] {len(res.sources)} authorized chunks retrieved.")
        else:
            print("  |-- [Sources] 0 chunks authorized. Access restricted.")

        print("\n[LLM RESPONSE]")
        print("-" * 20)
        print(res.answer)
        print("-" * 20)

    await pipe.close()
    print("\n[Demo Session Terminated]")

if __name__ == "__main__":
    try:
        asyncio.run(interactive_demo())
    except KeyboardInterrupt:
        pass
