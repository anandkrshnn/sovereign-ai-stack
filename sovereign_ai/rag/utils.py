import re
from typing import List, Dict
from .config import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP

class RecursiveCharacterTextSplitter:
    def __init__(
        self, 
        chunk_size: int = DEFAULT_CHUNK_SIZE, 
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        separators: List[str] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", " ", ""]

    def split_text(self, text: str) -> List[str]:
        """Split text recursively into chunks of specified size with overlap."""
        final_chunks = []
        
        # Initial pass
        current_text = text
        while current_text:
            if len(current_text) <= self.chunk_size:
                final_chunks.append(current_text)
                break
            
            # Find best separator to split
            split_idx = self._find_split_point(current_text)
            
            chunk = current_text[:split_idx]
            final_chunks.append(chunk)
            
            # Move ahead with overlap
            current_text = current_text[max(0, split_idx - self.chunk_overlap):]
            
            # Simple guard to prevent infinite loops if splitter doesn't progress
            if split_idx == 0:
                final_chunks.append(current_text[:self.chunk_size])
                current_text = current_text[self.chunk_size:]
                
        return final_chunks

    def _find_split_point(self, text: str) -> int:
        """Find the last separator within the chunk_size limit."""
        for sep in self.separators:
            # Look for separator in the target window [0, chunk_size]
            idx = text.rfind(sep, 0, self.chunk_size)
            if idx != -1:
                return idx + len(sep)
        
        # Fallback to hard cut at chunk_size
        return self.chunk_size

# --- Secret Training & Privacy Guardrails (v1.0.0-GA) ---

SECRET_PATTERNS = {
    "Generic API Key": r"(?i)(api[_-]?key|secret|token|auth)\s*[:=]\s*['\"]([a-zA-Z0-9_\-]{16,64})['\"]",
    "OpenAI Key": r"sk-[a-zA-Z0-9]{20,}",
    "AWS Key ID": r"(?<![A-Z0-9])[A-Z0-9]{20}(?![A-Z0-9])",
    "AWS Secret": r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])",
    "Bearer Token": r"Bearer\s+[a-zA-Z0-9\-\._~\+/]+=*",
    "PEM Private Key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
}

def find_secrets(text: str) -> List[Dict[str, str]]:
    """
    Scan text for common credential patterns. 
    Returns a list of matches with category and snippet.
    """
    found = []
    for category, pattern in SECRET_PATTERNS.items():
        matches = re.finditer(pattern, text)
        for m in matches:
            found.append({
                "category": category,
                "match": m.group(0),
                "start": m.start(),
                "end": m.end()
            })
    return found

def contains_secret(text: str) -> bool:
    """True if any secret patterns are detected in the text."""
    for pattern in SECRET_PATTERNS.values():
        if re.search(pattern, text):
            return True
    return False

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)
