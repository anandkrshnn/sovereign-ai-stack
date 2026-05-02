# 🛰️ Sovereign AI Stack: Research Preview FAQ

This FAQ is designed to clarify the current capabilities and future goals of the Sovereign AI Stack (v0.1.0-preview).

---

## 🏗️ Architecture & Vision

**Q: Why do I need a "Verified Airlock"? Isn't standard RAG enough?**
> **A:** Standard RAG is "best effort." For high-integrity use cases, you need to know if the model is hallucinating or ignoring context. Our "Verified Airlock" is a reference implementation of an automated local judge (using a small NLI cross-encoder) that scores every answer for grounding before it leaves the stack.

**Q: How is this different from LangChain or LlamaIndex?**
> **A:** We aren't a generic application framework; we are a **local-first governance stack**. While LangChain is great for building agents, the Sovereign AI Stack focuses on the *controls* around them: audit trails, attribute-based access control (ABAC), and verifiable grounding.

---

## 🛡️ Security & Forensics

**Q: What is a "Hardware-Anchored Local Anchor"?**
> **A:** This is a roadmap item (Q3 2026). The goal is to "staple" audit logs to signatures stored in a hardware secure enclave (TPM/Keyring) so that logs cannot be deleted or modified without detection. Currently, the stack provides a local cryptographic hash chain as a software-level baseline.

**Q: Is the grounding judge production-ready?**
> **A:** No. As of v0.1.0-preview, we have replaced the experimental generative judge with a deterministic NLI cross-encoder. This provides a much more reliable signal for grounding (entailment probability), but it should still be treated as an alpha feature for evaluation, not a certified safety guarantee.

---

## 💼 Business & Compliance

**Q: Is this HIPAA or SOC2 compliant?**
> **A:** No. The Sovereign AI Stack is a **reference implementation**, not a certified product. It is designed to demonstrate how one *could* build a system that meets the technical safeguard requirements of HIPAA or the audit requirements of SOC2, but using the stack does not grant compliance.

**Q: How can I contribute?**
> **A:** We are looking for contributors to help with the core NLI verifier, hardware attestation layers, and performance benchmarking. See [ROADMAP.md](ROADMAP.md) for current priorities.

---
*Last updated: 2026-05-02*  
🛰️ *Building the foundation for verifiable AI sovereignty.*
