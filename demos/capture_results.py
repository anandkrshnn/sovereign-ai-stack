import asyncio
import importlib.util
import os
import sys
import json
from datetime import datetime

# Add root to path
sys.path.append(os.getcwd())

async def run_scenario(name):
    print(f"Capturing Scenario: {name}...")
    module_path = f"demos/{name}/demo.py"
    spec = importlib.util.spec_from_file_location(f"demo_{name}", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Capture print output
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = result_buffer = StringIO()
    
    await module.run_demo()
    
    sys.stdout = old_stdout
    return result_buffer.getvalue()

async def main():
    results = {
        "timestamp": datetime.now().isoformat(),
        "scenarios": []
    }
    
    # Run setup first
    from demos import setup_data
    await setup_data.main()
    
    scenarios = ["healthcare", "finance", "engineering"]
    for s in scenarios:
        output = await run_scenario(s)
        results["scenarios"].append({
            "id": s,
            "name": s.capitalize(),
            "output": output,
            "status": "PASS" if "BLOCK" in output or "ALLOWED" in output else "FAIL"
        })
    
    with open("demos/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results captured to demos/results.json")

if __name__ == "__main__":
    asyncio.run(main())
