# 🛰️ Sovereign AI Stack: Launch FAQ & Quick Answers

Use these pre-written responses for common questions during the HackerNews, LinkedIn, and Reddit launch.

---

## 🏗️ Architecture & Vision

**Q: Why do I need a "Verified Airlock"? Isn't standard RAG enough?**
> **A:** Standard RAG is "best effort." In regulated industries (Healthcare/Finance), best effort isn't enough. The Verified Airlock ensures that *nothing* unverified or unauthorized reaches the user. We integrate a mandatory local judge model that scores every answer for grounding before it leaves the stack.

**Q: How is this different from LangChain or LlamaIndex?**
> **A:** We aren't a generic framework; we are a **governance-first platform**. While LangChain is great for prototyping, the Sovereign AI Stack is designed for production forensics. We include hardware-bound audit trails, multi-tenant physical isolation, and GAIP-2030 compliance out of the box.

---

## 🛡️ Security & Forensics

**Q: What is a "Hardware-Bound Local Anchor"?**
> **A:** It’s our solution to the "God Mode" operator problem. Even if an attacker has filesystem access, they can't delete or truncate the audit logs without detection. We "staple" the latest audit hash to a signature stored in the OS Secure Enclave (TPM/Keyring). If the log is tampered with, the anchor mismatch triggers an immediate forensic alert.

**Q: How do you handle non-repudiation if the host is wiped?**
> **A:** That’s where the **Remote Anchor** comes in. v1.0.0-GA is "Remote-Ready," with hooks to periodically pin the chain head to a remote Git repo, IPFS, or a blockchain. This proves the audit trail existed even if the local machine is destroyed.

---

## 💻 Developer Experience

**Q: Can I use my existing OpenAI-compatible apps?**
> **A:** Yes! The Sovereign Bridge exposes a `/v1/chat/completions` endpoint. Just change your `base_url` to point to the Sovereign Stack, and your app is instantly upgraded with governance and forensic auditing.

**Q: What models do you support?**
> **A:** We are model-agnostic but optimized for local inference. We recommend **Qwen 2.5** or **Llama 3** running via Ollama for the best balance of speed and grounding accuracy.

---

## 💼 Business & Compliance

**Q: Is this HIPAA or SOC2 compliant?**
> **A:** The stack is designed to provide the *forensic evidence* required for HIPAA and SOC2. By providing a tamper-evident, cryptographically-linked audit trail of every AI interaction, we significantly reduce the "Compliance Tax" for enterprise AI deployments.

**Q: How do you monetize?**
> **A:** The core stack is MIT-licensed. We monetize through **Enterprise Pilots**, managed deployments, and custom forensic integration services for large-scale regulated workloads.

---
*Last updated: 2026-04-27*  
🛰️ *Sovereignty is the new safety.*
