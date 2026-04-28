import os

def replace_in_file(file_path, search_text, replace_text):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if search_text in content:
        new_content = content.replace(search_text, replace_text)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated: {file_path}")

def main():
    root_dir = r"c:\Users\Monika\Documents\GitHub\sovereign-ai-stack\sovereign_ai"
    
    # 1. Fix old package names in code
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                replace_in_file(file_path, "from local_verify", "from sovereign_ai.verify")
                replace_in_file(file_path, "from local_rag", "from sovereign_ai.rag")
                replace_in_file(file_path, "import local_rag", "import sovereign_ai.rag")
                replace_in_file(file_path, "RAGPipeline", "SovereignPipeline")

    # 2. Fix the database path in config.py
    config_file = os.path.join(root_dir, "rag", "config.py")
    if os.path.exists(config_file):
        replace_in_file(config_file, "local_rag.db", "sovereign.db")

if __name__ == "__main__":
    main()
