import argparse
import sys
from sovereign_ai.common.audit import SovereignAuditLogger


def main():
    parser = argparse.ArgumentParser(
        description="Offline cryptopgrahic verification of Sovereign Audit Chains."
    )
    parser.add_argument("--tenant", required=True, help="Tenant ID to verify.")
    parser.add_argument(
        "--base-dir", default="data", help="Base directory containing the tenant's logs."
    )

    args = parser.parse_args()

    print(f"Starting offline verification for tenant: {args.tenant}")
    print(f"Checking ledger path: {args.base_dir}/{args.tenant}_audit.jsonl")

    try:
        logger = SovereignAuditLogger(args.base_dir, args.tenant)
        is_valid = logger.verify_integrity()

        if is_valid:
            print(f"\n[OK] Audit chain for tenant '{args.tenant}' is VALID (100% Integrity).")
            print("Cryptographic signatures and Merkle hashes match the anchor.")
            sys.exit(0)
        else:
            print(
                f"\n[FAIL] CRITICAL: Audit chain for tenant '{args.tenant}' is CORRUPTED or TAMPERED!"
            )
            sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] Verification failed due to exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
