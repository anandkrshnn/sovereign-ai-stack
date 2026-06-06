import asyncio
import json
import os
import shutil
from unittest.mock import AsyncMock

import pytest
import yaml

from sovereign_ai.bridge.orchestrator import SovereignOrchestrator
from sovereign_ai.bridge.schemas import ChatCompletionRequest, ChatMessage
from sovereign_ai.common.schemas import SecurityHalt


@pytest.fixture
def base_dir():
    path = "test_phase3_data"
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    yield path
    if os.path.exists(path):
        shutil.rmtree(path)


@pytest.mark.asyncio
async def test_runtime_enforcement_logic(base_dir):
    tenant_id = "phase3-tenant"
    principal = "anonymous"

    policy_dir = os.path.join(base_dir, tenant_id, "policies")
    os.makedirs(policy_dir, exist_ok=True)

    policies = {
        "version": "1.1.0a5",
        "allow": [
            {"principal": principal, "resource": "vault", "action": "query", "effect": "allow"}
        ],
        "deny": [
            {
                "principal": principal,
                "resource": "filesystem",
                "action": "execute",
                "effect": "deny",
            }
        ],
    }
    with open(os.path.join(policy_dir, f"{principal}.yaml"), "w") as f:
        yaml.dump(policies, f)

    orchestrator = SovereignOrchestrator(base_dir=base_dir)

    from sovereign_ai.rag.schemas import Document

    rag = await orchestrator._get_rag_instance(tenant_id, principal)
    await rag.ingest(
        [
            Document(
                doc_id="1",
                source="test-source",
                content="The vault is safe and secure.",
                tenant_id=tenant_id,
            )
        ]
    )

    # A. Authorized Query
    req_allow = ChatCompletionRequest(
        model="test",
        messages=[ChatMessage(role="user", content="Tell me about the vault.")],
        sovereign_principal=principal,
        use_cache=False,
    )
    # We mock the LLM call to return exactly what's in the ingestion context
    orchestrator._call_llm_atomic = AsyncMock(return_value="The vault is safe and secure.")

    # Force evaluator to PASS
    orchestrator.evaluator.evaluate = lambda q, c, a: {
        "grounding_score": 0.99,
        "faithfulness_score": 0.99,
        "overall_score": 0.99,
        "passed": True,
    }

    resp = await orchestrator.complete(req_allow, tenant_id)
    assert "The vault is safe" in resp.choices[0].message.content
    print("Pre-generation allow and Grounding verified.")

    # B. Unauthorized Execution (Inferred as 'execute' on 'filesystem')
    req_deny = ChatCompletionRequest(
        model="test",
        messages=[ChatMessage(role="user", content="Save a file to the filesystem.")],
        sovereign_principal=principal,
    )

    resp_deny = await orchestrator.complete(req_deny, tenant_id)
    assert "Access Denied" in resp_deny.choices[0].message.content
    assert "Formal policy verification rejected" in resp_deny.choices[0].message.content
    print("Pre-generation deny verified.")

    await orchestrator.close()


@pytest.mark.asyncio
async def test_security_halt_monitoring(base_dir):
    tenant_id = "halt-tenant"
    policy_dir = os.path.join(base_dir, tenant_id, "policies")
    os.makedirs(policy_dir, exist_ok=True)

    # Start with a clean policy
    with open(os.path.join(policy_dir, "alice.yaml"), "w") as f:
        yaml.dump(
            {
                "allow": [
                    {
                        "principal": "alice",
                        "resource": "vault",
                        "action": "query",
                        "effect": "allow",
                    }
                ]
            },
            f,
        )

    orchestrator = SovereignOrchestrator(base_dir=base_dir)

    # Initial request should work
    req = ChatCompletionRequest(
        model="test", messages=[ChatMessage(role="user", content="hi")], sovereign_principal="alice"
    )
    orchestrator._call_llm_atomic = AsyncMock(return_value="hi")
    await orchestrator.complete(req, tenant_id)

    # 2. Inject a CONFLICT manually (simulating malicious edit)
    # Principal 'any' denies what Alice is allowed
    with open(os.path.join(policy_dir, "any.yaml"), "w") as f:
        yaml.dump(
            {
                "deny": [
                    {"principal": "any", "resource": "vault", "action": "query", "effect": "deny"}
                ]
            },
            f,
        )

    # Trigger background monitor manually
    await orchestrator._monitor_tenant_policies(tenant_id)

    assert tenant_id in orchestrator._halted_tenants
    print("Security Halt triggered successfully.")

    # Next request should raise SecurityHalt
    with pytest.raises(SecurityHalt):
        await orchestrator.complete(req, tenant_id)
    print("Security Halt enforcement verified.")

    await orchestrator.close()


if __name__ == "__main__":
    asyncio.run(test_runtime_enforcement_logic("test_phase3_data_1"))
    asyncio.run(test_security_halt_monitoring("test_phase3_data_2"))
    print("Phase 3 Runtime Tests Passed!")
