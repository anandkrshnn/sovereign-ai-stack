import hashlib
from typing import List, Optional

class MerkleTree:
    """
    Implements a Merkle Tree for efficient proof-of-inclusion and history auditing.
    Addresses the 'Basic Pattern' criticism by moving from linear chains to 
    aggregated cryptographic trees (standard for high-integrity systems).
    """
    def __init__(self, leaves: List[str]):
        self.leaves = [self._hash(l) for l in leaves]
        self.tree = self._build_tree(self.leaves)

    def _hash(self, data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    def _build_tree(self, nodes: List[str]) -> List[List[str]]:
        """Recursively builds the tree layers until the root."""
        layers = [nodes]
        while len(layers[-1]) > 1:
            current_layer = layers[-1]
            next_layer = []
            for i in range(0, len(current_layer), 2):
                left = current_layer[i]
                right = current_layer[i+1] if i+1 < len(current_layer) else left
                next_layer.append(self._hash(left + right))
            layers.append(next_layer)
        return layers

    @property
    def root(self) -> str:
        return self.tree[-1][0] if self.tree else ""

    def get_proof(self, index: int) -> List[dict]:
        """
        Generates a Merkle Proof for a leaf at a given index.
        Proof is O(log n), allowing for efficient remote verification.
        """
        proof = []
        for i in range(len(self.tree) - 1):
            layer = self.tree[i]
            is_right = index % 2
            sibling_index = index - 1 if is_right else index + 1
            
            if sibling_index < len(layer):
                proof.append({
                    "position": "left" if is_right else "right",
                    "hash": layer[sibling_index]
                })
            else:
                # Sibling is self (odd leaf count)
                proof.append({
                    "position": "right",
                    "hash": layer[index]
                })
            index //= 2
        return proof

    @staticmethod
    def verify_proof(leaf: str, proof: List[dict], root: str) -> bool:
        """Verifies a leaf against a root using a Merkle Proof."""
        current_hash = hashlib.sha256(leaf.encode()).hexdigest()
        for p in proof:
            if p["position"] == "left":
                current_hash = hashlib.sha256((p["hash"] + current_hash).encode()).hexdigest()
            else:
                current_hash = hashlib.sha256((current_hash + p["hash"]).encode()).hexdigest()
        return current_hash == root

if __name__ == "__main__":
    leaves = ["event_1", "event_2", "event_3", "event_4"]
    tree = MerkleTree(leaves)
    print(f"Merkle Root: {tree.root}")
    
    proof = tree.get_proof(2) # event_3
    print(f"Proof for event_3: {proof}")
    
    is_valid = MerkleTree.verify_proof("event_3", proof, tree.root)
    print(f"Verification: {is_valid}")
