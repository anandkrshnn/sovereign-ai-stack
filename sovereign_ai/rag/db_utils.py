import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from sqlcipher3 import dbapi2 as sqlcipher
except ImportError:
    sqlcipher = None

def get_db_status(db_path: str, password: Optional[str] = None) -> Dict[str, Any]:
    """
    Check if a database is encrypted, reachable, and its stats.
    """
    path = os.path.abspath(db_path)
    if not os.path.exists(path):
        return {"exists": False}
        
    status = {
        "exists": True,
        "path": path,
        "encrypted": False,
        "accessible": False,
        "error": None
    }
    
    # 1. Check if it's a standard plaintext DB
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        cur.fetchone()
        status["accessible"] = True
        status["encrypted"] = False
        conn.close()
        return status
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        status["encrypted"] = True

    # 2. If encrypted, try SQLCipher
    if password:
        if sqlcipher is None:
            status["error"] = "sqlcipher3-wheels not installed"
            return status
            
        try:
            conn = sqlcipher.connect(path)
            # Use space-padded = for readability, match debug script
            escaped_pass = password.replace("'", "''")
            conn.execute(f"PRAGMA key = '{escaped_pass}'")
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            cur.fetchone()
            status["accessible"] = True
            conn.close()
        except Exception as e:
            status["accessible"] = False
            status["error"] = f"Unlock failed: {str(e)}"
            
    return status

def encrypt_database(src: str, dst: str, password: str):
    """
    Migrate a plaintext database to an encrypted SQLCipher one.
    """
    if sqlcipher is None:
        raise ImportError("sqlcipher3-wheels required for encryption.")
        
    src_abs = os.path.abspath(src)
    dst_abs = os.path.abspath(dst)
    
    if not os.path.exists(src_abs):
        raise FileNotFoundError(f"Source database not found: {src_abs}")
    if os.path.exists(dst_abs):
        raise FileExistsError(f"Target path already exists: {dst_abs}")

    # Use SQLCipher driver to open source (it can handle plaintext)
    conn = sqlcipher.connect(src_abs)
    
    try:
        # ATTACH + KEY is the atomic encryption path. 
        # Debugged syntax: single quotes around absolute path and password.
        sql = f"ATTACH DATABASE '{dst_abs}' AS encrypted_db KEY '{password}'"
        conn.execute(sql)
        conn.execute("SELECT sqlcipher_export('encrypted_db')")
        conn.execute("DETACH DATABASE encrypted_db")
        conn.commit()
    finally:
        conn.close()

def decrypt_database(src: str, dst: str, password: str):
    """
    Migrate an encrypted SQLCipher database back to plaintext SQLite.
    """
    if sqlcipher is None:
        raise ImportError("sqlcipher3-wheels required for decryption.")
        
    src_abs = os.path.abspath(src)
    dst_abs = os.path.abspath(dst)
    
    if os.path.exists(dst_abs):
        raise FileExistsError(f"Target path already exists: {dst_abs}")

    conn = sqlcipher.connect(src_abs)
    try:
        escaped_pass = password.replace("'", "''")
        conn.execute(f"PRAGMA key = '{escaped_pass}'")
        
        # Attach with empty key for plaintext
        sql = f"ATTACH DATABASE '{dst_abs}' AS plaintext_db KEY ''"
        conn.execute(sql)
        conn.execute("SELECT sqlcipher_export('plaintext_db')")
        conn.execute("DETACH DATABASE plaintext_db")
        conn.commit()
    finally:
        conn.close()

def rekey_database(db_path: str, old_password: str, new_password: str):
    """
    Rotate the encryption key for a SQLCipher database.
    """
    if sqlcipher is None:
        raise ImportError("sqlcipher3-wheels required for rekeying.")
    
    path_abs = os.path.abspath(db_path)
    conn = sqlcipher.connect(path_abs)
    
    try:
        escaped_old = old_password.replace("'", "''")
        escaped_new = new_password.replace("'", "''")
        conn.execute(f"PRAGMA key = '{escaped_old}'")
        conn.execute(f"PRAGMA rekey = '{escaped_new}'")
        conn.commit()
    finally:
        conn.close()
