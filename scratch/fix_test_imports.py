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
    
    # Files/Dirs to skip
    skip_dirs = {'.git', '.pytest_cache', '.benchmarks', '__pycache__', 'dist', 'build', '.cache'}
    
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            if file.endswith(('.py', '.yml', '.yaml', '.md', '.toml', '.html')):
                file_path = os.path.join(root, file)
                
                # Replace package name in imports and mocks
                replace_in_file(file_path, "sovereign_ai", "sovereign_ai")
                
                # Replace default DB name
                replace_in_file(file_path, "sovereign_ai.db", "sovereign.db")

if __name__ == "__main__":
    main()
