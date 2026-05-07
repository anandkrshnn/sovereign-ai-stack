from enum import Enum

class SigningAlgorithm(str, Enum):
    ED25519 = "ed25519"
    P256 = "p256"      # NIST Curve (TPM Compatible)

class RecordStatus(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"
    PASS = "pass"
    FAIL = "fail"
    SUCCESS = "success"
    EXEC_ERROR = "exec_error"
    PENDING = "pending"
