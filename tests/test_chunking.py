import pytest
from local_rag.utils import RecursiveCharacterTextSplitter, chunk_text

def test_basic_chunking():
    text = "Hello world. This is a test of the recursive splitter."
    chunks = chunk_text(text, chunk_size=20, chunk_overlap=5)
    
    assert len(chunks) > 1
    assert all(len(c) <= 25 for c in chunks) # 20 + some wiggle room for separators

def test_splitter_overlap():
    text = "Paragraph one structure. Paragraph two structure."
    splitter = RecursiveCharacterTextSplitter(chunk_size=30, chunk_overlap=15)
    chunks = splitter.split_text(text)
    
    # Check that both chunks contain the shared word due to overlap
    assert "structure" in chunks[0]
    assert "structure" in chunks[1]

def test_no_split_needed():
    text = "Short text."
    chunks = chunk_text(text, chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == text

def test_recursive_separators():
    # Should split on double newline first
    text = "Block A\n\nBlock B\n\nBlock C"
    chunks = chunk_text(text, chunk_size=10, chunk_overlap=0)
    
    assert "Block A" in chunks[0]
    assert "Block B" in chunks[1]
    assert "Block C" in chunks[2]
