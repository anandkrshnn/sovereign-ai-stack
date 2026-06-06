# Sovereign AI Stack (v0.2.0-alpha)

**Status: Research prototype. Not production-ready.**

This repository contains an experimental local-first AI pipeline with:
- NLI-based grounding gate (DeBERTa-v3 cross-encoder)
- Append-only audit log with Ed25519 signatures
- Local LLM inference via Ollama

See [LIMITATIONS.md](LIMITATIONS.md) for known failure modes before using.

## Running locally

```bash
pip install -e .
python -m sovereign_ai.pipeline
```

## Tests

```bash
pytest tests/
```

## License

MIT
