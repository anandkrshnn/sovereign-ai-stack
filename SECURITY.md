# Security Policy

## Supported Versions

Only the latest alpha release is currently supported for security updates.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

We take the security of the Sovereign AI Stack seriously. If you believe you have found a security vulnerability, please report it to us by:

1.  Opening a **Private Vulnerability Report** via GitHub's "Security" tab.
2.  Alternatively, email **ananda.krishnan@hotmail.com** with the subject `[SECURITY] <Vulnerability Summary>`.

Please provide a detailed description of the issue and steps to reproduce it. We will acknowledge your report within 48 hours and provide a timeline for resolution.

## Genesis Transition & Forensic Integrity

The `GENESIS_TRANSITION` protocol demonstrated in this research preview is designed to ensure forensic continuity across algorithm migrations (e.g., Ed25519 to P-256). 

**Important Disclaimers:**
- **Experimental Protocol**: This protocol is currently a reference implementation and is undergoing review for IETF RATS WG draft alignment.
- **Key Ceremony**: Chaining algorithm transitions ensures integrity of the *audit trail* but does not replace the need for secure hardware key ceremonies or formal root-of-trust provisioning.
- **Hardware Anchoring**: On Windows, the system utilizes the TPM via DPAPI or direct `ncrypt.dll` calls. Security properties depend on the underlying hardware's posture.
