from datetime import datetime
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field

class Document(BaseModel):
    """Extended with governance metadata for v0.2.0"""
    doc_id: str
    source: str
    title: Optional[str] = None
    content: str
    
    # Governance metadata
    classification: Optional[str] = None  # "public", "internal", "confidential", "secret"
    department: Optional[str] = None      # "finance", "hr", "engineering"
    tenant_id: Optional[str] = None       # Multi-tenancy support
    owner: Optional[str] = None           # Data owner/steward
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict = Field(default_factory=dict)

class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    position: int
    metadata: Dict = Field(default_factory=dict)

class SearchResult(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    score: float
    metadata: Dict = Field(default_factory=dict)

class PolicyDecision(BaseModel):
    """Policy enforcement verdict"""
    action: Literal["allow", "deny", "limit"]
    reason: str
    allowed_chunks: List[str] = Field(default_factory=list)  # chunk_ids
    denied_chunks: List[str] = Field(default_factory=list)   # chunk_ids
    limit_applied: Optional[int] = None

class AuditRecord(BaseModel):
    """Immutable audit log entry with cryptographic stapling for v0.3.0"""
    sequence_number: int = 0
    schema_version: str = "1"
    event_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    principal: str   # User/agent identifier
    query_hash: str  # SHA-256 of query
    query_preview: str
    
    # Decision details
    decision: PolicyDecision
    candidate_count: int      # FTS5 raw results
    allowed_count: int         # After policy filter
    denied_count: int
    allowed_doc_ids: List[str] = Field(default_factory=list)
    denied_doc_ids: List[str] = Field(default_factory=list)
    
    # Chain integrity fields
    prev_hash: Optional[str] = None
    curr_hash: Optional[str] = None

class RAGResponse(BaseModel):
    answer: str
    sources: List[SearchResult]
    model_name: str
    metadata: Dict = Field(default_factory=dict)
