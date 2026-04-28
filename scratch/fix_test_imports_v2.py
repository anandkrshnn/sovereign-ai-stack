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
    root_dir = r"c:\Users\Monika\Documents\GitHub\sovereign-ai-stack"
    
    # 1. Broadly replace sovereign_ai. with sovereign_ai.rag. in tests
    # (Since I already replaced local_rag with sovereign_ai in previous step)
    
    modules_to_move = [
        "store", "retriever", "main", "generator", "pipeline", 
        "schemas", "policy", "audit", "governed", "db_utils", 
        "hub", "utils", "reranker"
    ]
    
    for root, dirs, files in os.walk(os.path.join(root_dir, "tests")):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                for mod in modules_to_move:
                    # Fix imports
                    replace_in_file(file_path, f"from sovereign_ai.{mod}", f"from sovereign_ai.rag.{mod}")
                    replace_in_file(file_path, f"import sovereign_ai.{mod}", f"import sovereign_ai.rag.{mod}")
                    # Fix mocks
                    replace_in_file(file_path, f'patch("sovereign_ai.{mod}', f'patch("sovereign_ai.rag.{mod}')
                    replace_in_file(file_path, f'patch(\"sovereign_ai.{mod}', f'patch(\"sovereign_ai.rag.{mod}')

    # 2. Fix the bridge/main.py which I also touched
    bridge_file = os.path.join(root_dir, "sovereign_ai", "bridge", "main.py")
    if os.path.exists(bridge_file):
        replace_in_file(bridge_file, "from sovereign_ai import RAGPipeline", "from sovereign_ai.rag import RAGPipeline")

if __name__ == "__main__":
    main()
