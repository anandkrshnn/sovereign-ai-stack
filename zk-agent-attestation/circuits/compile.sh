#!/bin/bash
# ============================================================
# Groth16 ZKP Build Pipeline — Sovereign AI Stack
# Proves patient eligibility without raw data egress
#
# Requirements:
#   - circom v2.1.0+   (https://docs.circom.io/getting-started/installation/)
#   - snarkjs v0.7.3+  (npm install -g snarkjs)
#   - Node.js v18+
#
# Tested on: Ubuntu 22.04, Intel NUC 12 Pro (i7-1260P), TPM 2.0
# ============================================================

set -e

echo "=== [1/5] Compiling AgentAgeEligibility circuit ==="
circom agent_prover.circom --r1cs --wasm --sym
echo "    Constraints: $(snarkjs r1cs info agent_prover.r1cs | grep 'Constraints')"

echo ""
echo "=== [2/5] Generating witness from input ==="
# Sample input: patient age=25, study minimum=18
echo '{"age": "25", "minRequired": "18"}' > input.json
node agent_prover_js/generate_witness.js \
    agent_prover_js/agent_prover.wasm \
    input.json \
    witness.wtns

echo ""
echo "=== [3/5] Groth16 Setup (Powers of Tau) ==="
# Use a pre-generated ptau file for reproducibility
# Download: https://hermez.s3-eu-west-1.amazonaws.com/powersOfTau28_hez_final_12.ptau
if [ ! -f "pot12_final.ptau" ]; then
    echo "    Downloading Powers of Tau (12) ceremonial file..."
    curl -L https://hermez.s3-eu-west-1.amazonaws.com/powersOfTau28_hez_final_12.ptau \
        -o pot12_final.ptau
fi
snarkjs groth16 setup agent_prover.r1cs pot12_final.ptau agent_prover_0000.zkey
snarkjs zkey export verificationkey agent_prover_0000.zkey verification_key.json
echo "    Verification key exported to verification_key.json"

echo ""
echo "=== [4/5] Generating Groth16 proof ==="
START=$(date +%s%3N)
snarkjs groth16 prove agent_prover_0000.zkey witness.wtns proof.json public.json
END=$(date +%s%3N)
echo "    Proof generated in $((END - START))ms"
echo "    Proof saved to proof.json"

echo ""
echo "=== [5/5] Verifying proof ==="
snarkjs groth16 verify verification_key.json public.json proof.json
echo ""
echo "=== Pipeline complete. Zero raw patient data was transmitted. ==="
