import asyncio
import importlib.util
import os
import sys

# Get the directory of the current script
base_dir = os.path.dirname(os.path.abspath(__file__))

# Add root to path so demos can find sovereign_ai
root_dir = os.path.dirname(base_dir)
sys.path.append(root_dir)

async def run_setup():
    print("[Setup] Initializing Sovereign Demo Environments...")
    # Import setup_data dynamically from same dir
    spec = importlib.util.spec_from_file_location("setup_data", os.path.join(base_dir, "setup_data.py"))
    setup_data = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup_data)
    await setup_data.main()

async def run_scenario(name):
    print(f"\n--- Scenario: {name.upper()} ---")
    module_path = os.path.join(base_dir, name, "demo.py")
    spec = importlib.util.spec_from_file_location(f"demo_{name}", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    await module.run_demo()

async def main():
    print("[Sovereign AI Stack] Production-Ready Demos (v1.0.0-GA)")
    print("==========================================================")
    
    await run_setup()
    
    await run_scenario("healthcare")
    await run_scenario("finance")
    await run_scenario("engineering")
    
    print("\nSUCCESS: All Sovereign Scenarios Verified.")
    print("Forensic traces stored in per-tenant audit logs.")

if __name__ == "__main__":
    asyncio.run(main())
