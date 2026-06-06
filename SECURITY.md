# Security Policy & Adversarial Bounty

Sovereign AI Stack takes security and cryptographic integrity as its absolute highest priority. We practice a **Verify-First** approach and operate a zero-tolerance policy for "Security Theater."

## Supported Versions

| Version | Supported          | Notes |
| ------- | ------------------ | ----- |
| 2.x     | :white_check_mark: | Active Development & Hardening |
| 1.x     | :white_check_mark: | Maintenance & Bugfixes |
| 0.x     | :x:                | Deprecated |

## Reporting a Vulnerability

Please report vulnerabilities directly via GitHub Security Advisories or by emailing `security@sovereign-ai-stack.org`. We will acknowledge receipt within 48 hours and provide a timeline for triage.

## 🏆 Sovereign Adversarial Bounty

To enforce our commitment to verifiable, tamper-evident AI, we operate an active **Adversarial Bounty Program**.

### In Scope
We offer bounties for verifiable exploits targeting:
- **Cryptographic Bypasses**: Forging Ed25519 signatures or Merkle proofs.
- **TPM Spoofing**: Bypassing the `SOVEREIGN_ENV=production` guard to force software simulation in production, or extracting sealed keys from TPM context without authorization.
- **NLI Threshold Circumvention**: Finding adversarial prompts that trick the cross-encoder into confirming entailment (`contradiction < threshold`) for demonstrably hallucinated facts.
- **Audit Log Tampering**: Successfully truncating or rewriting the `SignedAuditChain` without detection.

### Out of Scope
The following are NOT eligible for bounty rewards:
- Volumetric Denial of Service (DoS) attacks against the LLM provider API.
- General framework bugs unrelated to the security airlock (e.g., LangChain core issues, Gradio UI bugs).
- Phishing, social engineering, or physical attacks on the host machine.
- Theoretical issues without a reproducible Proof of Concept (PoC).

We welcome red-teamers and security researchers to challenge the Sovereign AI Stack. Good luck.
