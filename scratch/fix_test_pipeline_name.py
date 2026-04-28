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
    
    for root, dirs, files in os.walk(os.path.join(root_dir, "tests")):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                replace_in_file(file_path, "RAGPipeline", "SovereignPipeline")
                # Also ensure local_verify is fixed in tests if any left
                replace_in_file(file_path, "local_verify", "sovereign_ai.verify")

if __name__ == "__main__":
    main()
