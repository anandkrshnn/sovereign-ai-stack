# Tamil Nadu e-Sevai case-file update slice

This constrained slice proves one regulated write: updating a Tamil Nadu
e-Sevai case file. It is not a claim that the repository integrates with the
Tamil Nadu government system. The selected action is `case_file.update`
because the repository has no existing certificate-issuance or vendor-payment
connector.

The path is deterministic:

`propose -> OPA-compatible policy decision -> operator approval/deny -> webhook execution/block -> Ed25519 evidence envelope`

The webhook is the only adapter path in this slice. n8n may submit or
transport a request, but it cannot authorize it. The trust-plane policy and
approval decision are authoritative.

Ollama is the selected optional runtime for proposal generation. The current
workflow uses a deterministic proposal function in CI and can inject an
Ollama-backed proposer later; no external model or network is required for
the conformance path. An external Ollama run is not claimed as validated here.

## Clean-machine five steps

```bash
git clone https://github.com/anandkrshnn/sovereign-ai-stack.git
cd sovereign-ai-stack
python -m venv .venv
.venv\Scripts\activate  # Windows; use source .venv/bin/activate on POSIX
python -m pip install -e .
```

Create one approved signed run, one denied run, and replay both from the
standalone verifier:

```bash
python -m sovereign_ai.workflows.tamilnadu_cli submit --output pending.json
python -m sovereign_ai.workflows.tamilnadu_cli approve --input pending.json --output approved.json --principal operator-1
python verify.py approved.json
python -m sovereign_ai.workflows.tamilnadu_cli submit --deny --output denied.json
python verify.py denied.json || echo "denied as expected"
```

The test writes no trusted state outside its temporary directory. Hardware
backing is required for production; simulator-backed tests are explicitly
non-production.
