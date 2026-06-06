import asyncio
import gradio as gr

# Sovereign AI Stack Core Modules (Brutal Minimalism)
from sovereign_ai.common.hardware_trust import get_secure_anchor
from sovereign_ai.verify.evaluator import SovereignEvaluator
from sovereign_ai.common.ledger_db import DatabaseAuditChain
from sovereign_ai.common.merkle import verify_proof_async

# Global initialization
anchor = get_secure_anchor("ptv-web-demo-tenant")
evaluator = SovereignEvaluator()
audit_chain = DatabaseAuditChain("ptv-web-demo-tenant", "sqlite+aiosqlite:///ptv_web_demo_ledger.sqlite", anchor)

# Pre-warm Evaluator model weights
import threading
threading.Thread(target=evaluator._ensure_model, daemon=True).start()

async def run_ptv_demo(query: str, context: str, tamper: bool = False):
    """Core PTV Airlock execution for Gradio interface"""
    try:
        # Initialize the DB Ledger lazily for the demo (must be in event loop)
        await audit_chain.initialize()
        
        model_output = "PTV provides cryptographic hardware attestation and zero-knowledge proofs for GAIP compliance."

        # 1. PROVE: Hardware Attestation
        quote = await asyncio.to_thread(anchor.generate_quote, "nonce123", [0, 11])

        # 2. TRANSFORM: Policy + NLI Grounding
        eval_res = await evaluator.evaluate_with_threshold_async(query, context, model_output, threshold=0.85)
        passed = eval_res["passed"]
        nli_score = eval_res["grounding_score"]

        # 3. VERIFY: Merkle append
        record_idx = await audit_chain.append_record("PTV_TRANSFORM", {
            "query": query, 
            "nli_score": nli_score,
            "passed": passed
        })
        proof = await audit_chain.get_audit_proof(record_idx)
        
        merkle_root = proof["root_hash"]
        leaf_hash = proof["leaf_hash"]
        merkle_path = proof["proof"]

        # Optional Tamper simulation
        if tamper:
            leaf_hash = "tampered_fake_leaf_hash_" + "x" * 20
        
        is_valid = await verify_proof_async(leaf_hash, merkle_path, merkle_root)

        nli_gauge = f"{nli_score:.2f} / 1.00 {'🟢 PASS' if passed else '🔴 FAIL-CLOSED'}"
        final_response = model_output if passed and is_valid else "⛔ [Sovereign Access Denied] Hallucination or Tampering Detected"
        status = "✅ MATHEMATICAL VERIFICATION SUCCESS" if (passed and is_valid) else "⛔ FAIL-CLOSED — Tamper / Low Confidence Detected"
        
        return (
            final_response,
            nli_gauge,
            quote.signature[:120] + "..." if quote else "TPM Quote",
            merkle_root[:64],
            status
        )
    except Exception as e:
        return ("Error", "N/A", str(e)[:100], "N/A", "Pipeline Initialization Failed")

def create_ptv_web_ui():
    with gr.Blocks(title="Sovereign AI Stack — PTV Verified Airlock", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🛡️ PTV Verified Airlock Demo\n**Prove → Transform → Verify** with TPM 2.0, NLI Gate (0.85), and Merkle Chains")
        
        with gr.Row():
            with gr.Column(scale=2):
                query_input = gr.Textbox(label="Query", value="Explain benefits of PTV for GAIP-2030 compliance", lines=2)
                context_input = gr.Textbox(label="Context / Documents", value="PTV enables hardware-rooted zero-knowledge attestation without exposing raw data.", lines=4)
                tamper_checkbox = gr.Checkbox(label="Simulate Tamper Attack (Red Team Test)", value=False)
                submit_btn = gr.Button("🚀 Run Verified Airlock", variant="primary")
            
            with gr.Column(scale=3):
                with gr.Row():
                    response_out = gr.Textbox(label="✅ Verified Response", lines=4)
                with gr.Row():
                    nli_out = gr.Textbox(label="📊 NLI Grounding Gauge")
                    tpm_out = gr.Textbox(label="🔐 TPM Attestation Quote")
                with gr.Row():
                    merkle_out = gr.Textbox(label="🌳 Merkle Root")
                    status_out = gr.Textbox(label="Verification Status")

        gr.Markdown("### How It Works (C4 Sequence)")
        gr.Markdown("""
        ```mermaid
        sequenceDiagram
            participant User
            participant Airlock as PTV Airlock
            participant TPM
            participant NLI
            participant Verifier
            User->>Airlock: Query + Context
            Airlock->>TPM: Prove (Hardware Quote)
            TPM-->>Airlock: Signed Quote
            Airlock->>NLI: Transform (0.85 Gate)
            NLI-->>Airlock: Score + Merkle Leaf
            Airlock->>Verifier: Verify Proof
            Verifier-->>User: Valid / Fail-Closed
        ```
        """)

        submit_btn.click(
            fn=run_ptv_demo,
            inputs=[query_input, context_input, tamper_checkbox],
            outputs=[response_out, nli_out, tpm_out, merkle_out, status_out]
        )

    return demo

if __name__ == "__main__":
    demo = create_ptv_web_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
