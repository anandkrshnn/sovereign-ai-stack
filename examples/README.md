# Sovereign AI Stack: Quickstart Examples

These examples demonstrate the core capabilities of the Sovereign AI Stack, ranging from basic retrieval to advanced forensic auditing.

## Example Directory

| File | What it demonstrates | Complexity | Recommended For |
| :--- | :--- | :--- | :--- |
| `01_basic_rag.py` | Minimal "Hello World" RAG pipeline | Low | First-time users |
| `02_verified_query.py` | The "Verified Airlock" (NLI Grounding) | Medium | Compliance officers, Devs |
| `03_forensic_agent.py` | Signed Audit Chains & Agentic Loops | High | Security Engineers |

## How to Run

1. **Install Dependencies**:
   Ensure you have the stack installed in your environment:
   ```bash
   pip install -e .
   ```

2. **Setup Local LLM (Optional for 01 & 03)**:
   The RAG and Agent examples expect a local Ollama instance running `qwen2.5:7b` (or your preferred model).
   ```bash
   ollama run qwen2.5:7b
   ```

3. **Execute**:
   ```bash
   python examples/01_basic_rag.py
   ```

## Key Concepts Demonstrated

- **Grounding Integrity**: Using DeBERTa-v3 cross-encoders to ensure LLMs don't hallucinate outside the provided context.
- **Forensic Non-Repudiation**: Using Ed25519 signatures and hash chains to create a tamper-evident audit trail of every AI decision.
- **Local Sovereignty**: All data, models, and keys remain on your hardware.
