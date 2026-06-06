# Sovereign AI Stack (v0.2.0-alpha)

**Status: Research prototype. Not production-ready.**

This repository contains an experimental local-first AI pipeline with:
- NLI-based grounding gate (DeBERTa-v3 cross-encoder)
- Append-only audit log with Ed25519 signatures
- Local LLM inference via Ollama

See [LIMITATIONS.md](LIMITATIONS.md) for known failure modes before using.

## Quickstart (Local Evaluation)

The entire stack runs locally. You will need [Ollama](https://ollama.com) installed and running.

1. **Install Ollama and pull the default model:**
   ```bash
   ollama serve &
   ollama pull mistral
   ```

2. **Install the package and dependencies:**
   ```bash
   pip install -e .[verify]
   ```

3. **Ingest a document:**
   ```bash
   echo "The launch code is 12345." > secret.txt
   sovereign ingest secret.txt --tenant demo-tenant
   ```

4. **Query the vault with verification:**
   ```bash
   sovereign ask "What is the launch code?" --tenant demo-tenant --verify
   ```

## Tests

```bash
pytest tests/
```

## License

MIT
