from pathlib import Path

# Paths
DEFAULT_DB_PATH = "sovereign_ai.db"
PROJECT_ROOT = Path(__file__).parent.parent

# Models
# Largest validated small-to-mid tier for local performance
# 1.5B is the baseline; 3B/7B are optional presets.
DEFAULT_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

# Retrieval
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_FTS_TOKENIZER = "porter unicode61 remove_diacritics 1"
DEFAULT_SNIPPET_TOKENS = 40

# Prompting
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful, precise local AI assistant. "
    "Answer the user query using only the provided context snippets. "
    "If the answer is not in the context, say that you don't know based on the provided material."
)

# Generation settings
GEN_MAX_NEW_TOKENS = 512
GEN_TEMPERATURE = 0.1
GEN_TOP_P = 0.9
