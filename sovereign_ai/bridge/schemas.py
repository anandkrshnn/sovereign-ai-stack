from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union, Tuple
from enum import Enum

class BackendType(str, Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"

class BackendConfig(BaseModel):
    url: str
    type: BackendType
    priority: int = 1 # 1 = highest, 10 = lowest
    is_healthy: bool = True

class TenantContext(BaseModel):
    tenant_id: str
    principal: str
    scopes: List[str] = []
    is_authenticated: bool = False

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    user: Optional[str] = None
    
    # Sovereign Extensions
    sovereign_principal: Optional[str] = Field(None, description="The principal ID for GAIP-2030 policy enforcement")
    sovereign_policy: Optional[str] = Field(None, description="Path to custom policy YAML")
    use_reranker: bool = Field(True, description="Whether to use v1.1.0 hybrid reranking (default: True)")
    use_cache: bool = Field(True, description="Whether to use v0.3.0 semantic caching (default: True)")

class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = "stop"

class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Usage = Field(default_factory=Usage)
    
    # Sovereign Metadata
    sovereign_meta: Optional[Dict[str, Any]] = None
