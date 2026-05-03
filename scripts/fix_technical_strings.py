import os
import re

def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Fix missed import strings in daemon commands
    content = content.replace('"-m", "localagent.api.app"', '"-m", "sovereign_ai.agent.api.app"')
    content = content.replace('"localagent.api.app"', '"sovereign_ai.agent.api.app"')
    
    # 2. Fix environment variables
    content = content.replace('LOCALAGENT_HOME', 'SOVEREIGN_AI_HOME')
    content = content.replace('LOCALAGENT_BRIDGE_SECRET', 'SOVEREIGN_AI_BRIDGE_SECRET')
    content = content.replace('LOCALAGENT_BRIDGE_ENABLED', 'SOVEREIGN_AI_BRIDGE_ENABLED')
    
    # 3. Fix names in Typer/FastAPI
    content = content.replace('name="localagent"', 'name="sovereign-ai-agent"')
    content = content.replace('title="LocalAgent Dashboard"', 'title="Sovereign AI Agent Dashboard"')
    
    # 4. Fix pipe names and sockets
    content = content.replace('localagent_v02', 'sovereign_ai_agent_v11')
    
    # 5. Specific fix for ipc.py missing imports (if not already fixed)
    if 'ipc.py' in path and 'import os' not in content:
        content = "import os\nimport asyncio\nfrom typing import Dict, Any, Optional\nfrom multiprocessing.connection import Listener, Client\n" + content

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

root_dir = r"c:\Users\Monika\Documents\GitHub\sovereign-ai-stack\sovereign_ai"
for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))

# Also fix tests
test_dir = r"c:\Users\Monika\Documents\GitHub\sovereign-ai-stack\tests"
for root, dirs, files in os.walk(test_dir):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))

print("Bulk technical string fix complete.")
