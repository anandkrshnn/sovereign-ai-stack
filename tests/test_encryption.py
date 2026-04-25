import pytest
import os
import sqlite3
from pathlib import Path
from local_rag.store import Store
from local_rag.db_utils import get_db_status, encrypt_database, decrypt_database, rekey_database
from local_rag.schemas import Document

try:
    from sqlcipher3 import dbapi2 as sqlcipher
except ImportError:
    sqlcipher = None

@pytest.fixture
def plaintext_db(tmp_path):
    db_path = tmp_path / "plain.db"
    # Ensure it's clean
    if db_path.exists(): db_path.unlink()
    
    from local_rag.retriever import FTS5Retriever
    retriever = FTS5Retriever(str(db_path))
    doc = Document(doc_id="d1", source="test", content="Secret sovereign context.")
    retriever.ingest([doc])
    retriever.store.close()
    return str(db_path)

@pytest.mark.skipif(sqlcipher is None, reason="sqlcipher3-wheels not installed")
def test_direct_encrypted_ingestion(tmp_path):
    db_path = tmp_path / "direct_secure.db"
    password = "secure-pass"
    
    from local_rag.main import LocalRAG
    rag = LocalRAG(db_path=str(db_path), password=password)
    
    doc = Document(doc_id="d2", source="test", content="Directly secure content.")
    rag.retriever.ingest([doc])
    rag.close()
    
    # Verify retrieval
    rag2 = LocalRAG(db_path=str(db_path), password=password)
    results = rag2.retriever.search("secure")
    assert len(results) == 1
    cleaned_text = results[0].text.replace("[result]", "").replace("[/result]", "")
    assert "Directly secure" in cleaned_text
    rag2.close()

@pytest.mark.skipif(sqlcipher is None, reason="sqlcipher3-wheels not installed")
def test_encryption_migration_and_retrieval(plaintext_db, tmp_path):
    encrypted_path = tmp_path / "secure.db"
    password = "sovereign-password"
    
    # 1. Encrypt
    encrypt_database(plaintext_db, str(encrypted_path), password)
    assert encrypted_path.exists()
    
    # 2. Verify SQLCipher can read it with password
    from local_rag.main import LocalRAG
    rag = LocalRAG(db_path=str(encrypted_path), password=password)
    # Give it a moment or ensure commit
    results = rag.retriever.search("sovereign")
    assert len(results) == 1
    cleaned_text = results[0].text.replace("[result]", "").replace("[/result]", "")
    assert "Secret sovereign" in cleaned_text
    rag.close()

@pytest.mark.skipif(sqlcipher is None, reason="sqlcipher3-wheels not installed")
def test_invalid_password_rejection(plaintext_db, tmp_path):
    encrypted_path = tmp_path / "auth_secure.db"
    encrypt_database(plaintext_db, str(encrypted_path), "correct-pass")
    
    from local_rag.main import LocalRAG
    with pytest.raises(PermissionError) as excinfo:
        LocalRAG(db_path=str(encrypted_path), password="wrong-pass")
    assert "Access Denied" in str(excinfo.value)

@pytest.mark.skipif(sqlcipher is None, reason="sqlcipher3-wheels not installed")
def test_key_rotation_rekey(plaintext_db, tmp_path):
    encrypted_path = tmp_path / "rekey_secure.db"
    old_pass = "old-pass"
    new_pass = "new-pass"
    
    encrypt_database(plaintext_db, str(encrypted_path), old_pass)
    
    # Rekey
    rekey_database(str(encrypted_path), old_pass, new_pass)
    
    # Verify old pass fails, new pass works
    from local_rag.main import LocalRAG
    with pytest.raises(PermissionError):
        LocalRAG(db_path=str(encrypted_path), password=old_pass)
        
    rag = LocalRAG(db_path=str(encrypted_path), password=new_pass)
    results = rag.retriever.search("sovereign")
    assert len(results) == 1
    cleaned_text = results[0].text.replace("[result]", "").replace("[/result]", "")
    assert "Secret sovereign" in cleaned_text
    rag.close()
