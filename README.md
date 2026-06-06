# Sovereign AI Stack (v0.2.0-alpha)

**Alpha-stage open-source framework for verifiable local AI.**

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI/CD](https://github.com/anandkrshnn/sovereign-ai-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/anandkrshnn/sovereign-ai-stack/actions/workflows/ci.yml)
[![SAST & Fuzzing](https://github.com/anandkrshnn/sovereign-ai-stack/actions/workflows/security.yml/badge.svg)](https://github.com/anandkrshnn/sovereign-ai-stack/actions/workflows/security.yml)
[![Status](https://img.shields.io/badge/status-Research_Preview-orange.svg)]()

> [!WARNING]
> **Status: Alpha / Research Preview**
> This repository is a research prototype. It is **not** yet a production-grade enterprise reference architecture. 
> Please read the [LIMITATIONS.md](docs/LIMITATIONS.md) and [KNOWN_GAPS.md](docs/KNOWN_GAPS.md) before evaluating this project. We publish our weaknesses (including NLI adversarial failure rates and TPM limitations) transparently.

## 🛡️ What is the Sovereign AI Stack?

The Sovereign AI Stack is a raw, experimental prototype exploring deterministic verification for local LLMs. It is built for researchers investigating zero-trust environments (e.g., Finance, Healthcare, Defense) and impending compliance standards like GAIP-2030.

This stack forces a strict **Verify-First** pipeline, exploring three mechanisms:

1. **NLI Grounding Gate**: A local DeBERTa-v3 cross-encoder gating claims based on logical entailment (Fail-Closed).
2. **Forensic Audit Chain**: An append-only JSONL log anchored via Ed25519 signatures.
3. **Hardware-Anchored Trust**: Keys bound to Native TPM 2.0 (ESYS) PCR states on Linux.

---

## 🚀 One-Command Quickstart

### Try the PTV Airlock Live (Browser Demo)

[![Open in Gradio](https://img.shields.io/badge/Try_Live_Demo-FF6B6B?logo=gradio)]()

Watch the NLI gate and Merkle verification in real time via an interactive Web UI.

```bash
# 1. Install via pip with demo dependencies
pip install -e .[demo]

# 2. Run the PTV Web UI
python -m examples.ptv_web_ui
```

### Run via Docker (Multi-Arch, TPM-Ready)
For minimal friction deployment, use our optimized GHCR image:

```bash
# Pull the latest slim runtime
docker pull ghcr.io/anandkrshnn/sovereign-ai-stack:latest

# Run the Web UI (Port 7860) or API Gateway (Port 8000)
docker run -p 7860:7860 ghcr.io/anandkrshnn/sovereign-ai-stack:latest
```

Or use Docker Compose for local TPM simulator integration:
```bash
docker-compose up -d
```

### Start the Local AI Gateway
```bash
python -m sovereign_ai.bridge.main
```

## 🧩 Ecosystem Integration: LangChain

The stack provides an experimental wrapper for any LangChain model or pipeline.

```python
from langchain_openai import ChatOpenAI
from sovereign_ai.langchain_guard import SovereignLangChainGuard

# Wrap your existing LLM
llm = ChatOpenAI(model="gpt-4")
guard = SovereignLangChainGuard(llm=llm, nli_threshold=0.85)

# Use as a standard LCEL Runnable.
chain = prompt | guard | StrOutputParser()
```

---

## 🤝 The Contributor Standard

We are building a community of pragmatic ML researchers, security engineers, and distributed systems developers. 

If you want to contribute, review our [Contributor Onboarding Guide](docs/CONTRIBUTOR_ONBOARDING_v2.0.md). We aim for:
- **Brutal Minimalism**: No over-engineering. We pruned the ReAct loops to purely linear, verifiable steps.
- **Defensive Design**: Write tests for the adversarial edge case, not just the happy path.
- **Mathematical Honesty**: Do not claim statistical probabilities are deterministic proofs. We publish our evasion rates.

## 📜 License
MIT
