from sovereign_ai.verify.policy_z3 import PolicyVerifier


def test_z3_conflicts():
    policies = [
        {"principal": "alice", "resource": "vault-1", "action": "read", "effect": "allow"},
        {"principal": "any", "resource": "vault-1", "action": "any", "effect": "deny"},
    ]

    verifier = PolicyVerifier()
    conflicts = verifier.detect_conflicts(policies)

    print(f"Detected Conflicts: {conflicts}")
    assert len(conflicts) > 0
    assert "alice" in conflicts[0]


def test_z3_reachability():
    policies = [
        {"principal": "alice", "resource": "vault-1", "action": "read", "effect": "allow"},
        {"principal": "bob", "resource": "vault-1", "action": "read", "effect": "deny"},
    ]

    verifier = PolicyVerifier()

    # Alice should be reachable
    alice_reachable = verifier.check_reachability("alice", "vault-1", policies)
    print(f"Alice reachable: {alice_reachable}")
    assert alice_reachable is True

    # Bob should NOT be reachable
    bob_reachable = verifier.check_reachability("bob", "vault-1", policies)
    print(f"Bob reachable: {bob_reachable}")
    assert bob_reachable is False


if __name__ == "__main__":
    test_z3_conflicts()
    test_z3_reachability()
    print("Z3 Tests Passed!")
