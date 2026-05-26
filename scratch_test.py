import cryptography.hazmat.primitives.asymmetric.ed25519 as ed
from sovereign_ai.immune.events import KnowledgeEvent
from sovereign_ai.immune.ptv_bridge import PTVBridge
from sovereign_ai.immune.brain import VerifiedBrain

pub = "822009aeb8ba99084675e8a901c5de1b26a5b3a7ad8cf66e32b08ac401442ae0"
priv = "e89e9f399e91e63c0a7c02609b1d9083a066310aac8e25abd7e22cf2686cab54"

brain = VerifiedBrain()
event = KnowledgeEvent(payload="test", source_author="test")
event.metadata["ptv_validated"] = True
event.metadata["tpm_attested"] = True
event.sign_event(priv)
print("sig:", event.signature)
print("verify:", event.verify_signature(pub))
