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
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m pip install -e .
```

Create one approved signed run, one denied run, and replay both from the
standalone verifier:

```bash
python -m sovereign_ai.workflows.tamilnadu_cli submit --output pending.json
python -m sovereign_ai.workflows.tamilnadu_cli export-trust --output trusted-signers.json
python -m sovereign_ai.workflows.tamilnadu_cli approve --input pending.json --output approved.json --principal operator-1
python verify.py approved.json --trusted-keys trusted-signers.json --tenant default
python -m sovereign_ai.workflows.tamilnadu_cli submit --deny --output denied.json
python verify.py denied.json --trusted-keys trusted-signers.json --tenant default
```

The test writes no trusted state outside its temporary directory. Hardware
backing is required for production; simulator-backed tests are explicitly
non-production.

The exported development registry comes from the configured simulator anchor,
not a key copied from an evidence envelope. Protect/provision production keys
out-of-band; this CLI explicitly rejects production, even with simulator opt-in.

Pending files are signature/digest/tenant/policy checked against that anchor
before approval and expire after five minutes. `load_pending` is the supported
rehydration operation; do not insert client documents into private runner state.
The principal string is an assertion by an authenticated host, not proof of a
human identity or a government integration.

Each real webhook is attempted once. `status="completed"` plus a nonempty
`receipt_id` is an adapter confirmation, not an independent exactly-once proof.
An explicit remote `status="blocked"` asserts non-execution. Lost responses,
exceptions, and missing confirmations yield signed `status="unknown"` with
`executed=null`; verification preserves that uncertainty. Simulator output is
explicitly labeled `"simulated"` and is not a real remote write.

Reservations prevent redispatch of a consumed run in one workflow instance,
but are not durable across instances/restarts. Do not reuse the CLI for
production writes: provision a durable host execution ledger and remote
idempotency/reconciliation before that integration. The standalone verifier
rejects v1 envelopes; regenerate preview fixtures as v2.

Verifier exit status zero means the signed evidence is valid and consistent,
not that a business action succeeded. Inspect `decision` and nullable
`executed`, especially for valid `"unknown"` or `"denied"` reports.
