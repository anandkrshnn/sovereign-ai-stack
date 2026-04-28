import os

def replace_in_file(file_path, old_text, new_text):
    if not os.path.exists(file_path):
        return
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if old_text in content:
        print(f"Updating {file_path}")
        new_content = content.replace(old_text, new_text)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

demo_dirs = ["demos", "demos/engineering", "demos/healthcare", "demos/finance"]

for d in demo_dirs:
    full_dir = os.path.join(os.getcwd(), d)
    if not os.path.exists(full_dir):
        continue
    for f in os.listdir(full_dir):
        if f.endswith(".py"):
            path = os.path.join(full_dir, f)
            replace_in_file(path, "RAGPipeline", "SovereignPipeline")

# Also check for incorrect imports like 'from sovereign_ai.rag import SovereignPipeline'
# Our unified export is 'from sovereign_ai import SovereignPipeline'
for d in demo_dirs:
    full_dir = os.path.join(os.getcwd(), d)
    if not os.path.exists(full_dir):
        continue
    for f in os.listdir(full_dir):
        if f.endswith(".py"):
            path = os.path.join(full_dir, f)
            replace_in_file(path, "from sovereign_ai.rag import SovereignPipeline", "from sovereign_ai import SovereignPipeline")
            replace_in_file(path, "from sovereign_ai.rag import Config", "from sovereign_ai import Config")
