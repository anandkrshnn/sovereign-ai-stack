# Contributing to Sovereign AI Stack

**Status: Research Preview (`1.1.0a2` alpha) — external scrutiny welcome.**

This is not a finished product. It is a reference implementation exploring deterministic verification and cryptographic forensics for local RAG pipelines. Contributions that challenge assumptions, expose weaknesses, or improve rigour are valued over feature additions.

---

## Where Help Is Most Needed

### 1. Adversarial Verification Testing
The NLI cross-encoder (`cross-encoder/nli-deberta-v3-base`) uses a fixed threshold. We need:
- Adversarial prompt pairs that expose threshold brittleness
- Calibration experiments (isotonic regression, Platt scaling)
- Benchmark datasets beyond the current synthetic suite

See: `tests/verify/test_evaluator_adversarial.py`

### 2. Threat Model Review
`docs/THREAT_MODEL.md` documents known risks. If you find a gap — an attack surface, a trust assumption we missed, or a mitigation that is weaker than claimed — open an issue with the label `threat-model`.

### 3. Hardware Attestation Research
The current forensic chain uses Ed25519 keys anchored to the OS keyring. The roadmap targets TPM 2.0 hardware binding. If you have experience with:
- `tpm2-pytss` / TPM 2.0 on Linux
- PKCS#11 hardware tokens
- Secure enclave attestation (SGX, TrustZone)

...we want to hear from you before writing the implementation.

### 4. Independent Benchmarking
`benchmark.py` reports p50/p95/p99 latency for the NLI airlock. Run it on your hardware and open an issue with results. Reproducible external benchmarks are the only credible ones.

---

## Ground Rules

- **Challenge claims.** If the README overstates a capability, open an issue. Honest scope is a design goal.
- **No feature PRs without prior issue.** Open an issue first, describe the problem, wait for acknowledgement.
- **Tests are mandatory.** Every code change must include or update a test in `tests/`.
- **Respect the alpha framing.** This is not production software. PRs that add disclaimers are as welcome as PRs that add features.

---

## Elite DevSecOps CI Expectations

We run a zero-trust, elite CI/CD pipeline. Your PR will be rejected if it fails any of the following automated gates:
1. **Lint & Format**: Code must pass `ruff`, `mypy` strict type checking, and `black`/`isort` formatting.
2. **Security SAST**: We run `bandit` and `semgrep` for cryptographic misuse, nonce reuse, and hardcoded secrets. 
3. **Fuzzing & Property Tests**: We use `hypothesis` to fuzz Merkle proofs and NLI boundaries.
4. **Crypto Smoke Tests**: E2E validation requires successful attestation against a simulated TPM 2.0 enclave.
5. **Performance Benchmark**: PRs that degrade NLI throughput or cryptographic hash speed will fail the regression gate.

### Prioritized Rollout Plan
To minimize disruption while we harden the repository, the CI/CD rollout will occur in phases:
- **Phase 1 (Current)**: PR Status Checks. All CI gates (SAST, Fuzzing, Linting) run on PRs as required status checks.
- **Phase 2**: Merge Queue. Introduce a strict merge queue requiring up-to-date linear history.
- **Phase 3**: Main Branch Gates. Daily scheduled jobs for dependency auditing (`trivy`, `pip-audit`) and secret scanning will automatically open issues and block releases.
- **Phase 4**: Secure Release. Fully automated OIDC PyPI publishing triggered by tagged releases.

---

## Development Setup

If you are looking to contribute to the v2.0 roadmap pillars, please refer to our comprehensive [Sovereign AI Stack v2.0 Contributor Onboarding Guide](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/docs/CONTRIBUTOR_ONBOARDING_v2.0.md) for architectural overviews, directory mappings, recommended tool suites, and implementation guidance.

Standard local setup:

```bash
git clone https://github.com/anandkrshnn/sovereign-ai-stack
cd sovereign-ai-stack
pip install -e ".[dev,agent,verify]"
pytest tests/ -m "not requires_model" -v
```

For the full NLI model suite (requires ~1GB download):
```bash
pytest tests/ -m "requires_model" -v
```

---

## Reporting Security Issues

Do not open a public issue for security vulnerabilities. Email directly: **ananda.krishnan@hotmail.com**

Include:
- Affected component (`agent`, `rag`, `verify`, `bridge`)
- Reproduction steps
- Your assessment of exploitability

---

## Code of Conduct

Technical rigour and intellectual honesty are the only norms here. Critique the work, not the person.
