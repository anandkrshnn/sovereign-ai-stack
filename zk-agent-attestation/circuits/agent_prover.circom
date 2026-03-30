pragma circom 2.1.0;

include "node_modules/circomlib/circuits/comparators.circom";

/*
 * AgentAgeEligibility Circuit
 *
 * Implements a Zero-Knowledge Range Proof for healthcare agent authorization.
 * Allows an agent to prove a patient meets eligibility criteria (e.g., Age >= 18)
 * without exposing the patient's actual birthdate to the central federation hub.
 *
 * This is the core of the Prove-Transform-Verify (PTV) model described in:
 * NIST NCCoE Public Comment — "Accelerating the Adoption of Software and
 * AI Agent Identity and Authorization", March 2026.
 *
 * Private inputs (never transmitted):  age
 * Public inputs (visible to verifier): minRequired
 * Output:                              isEligible (1 = eligible, 0 = not)
 */

template AgentAgeEligibility(limit) {
    signal input age;          // Private: The actual patient age
    signal input minRequired;  // Public: The study requirement
    signal output isEligible;  // Public: 1 if eligible, 0 if not

    component gt = GreaterThan(32);
    gt.in[0] <== age;
    gt.in[1] <== minRequired;

    isEligible <== gt.out;
}

component main {public [minRequired]} = AgentAgeEligibility(18);
