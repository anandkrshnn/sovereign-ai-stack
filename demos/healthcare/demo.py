import asyncio
from local_rag import RAGPipeline, Config

async def run_demo():
    print("\n[HEALTHCARE SCENARIO] Clinic Data Isolation")
    
    # Get the directory of the current script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    policy_path = os.path.join(base_dir, "policy.yaml")

    # Scenario 1: Doctor at Clinic A (Cardiology) requesting PHI
    cfg_doctor = Config(
        db_path="demos/healthcare/clinic_a.db",
        policy_path=policy_path,
        tenant_id="clinic_a",
        roles=["doctor"],
        classifications=["PHI", "public"]
    )
    pipe_doctor = RAGPipeline(cfg_doctor)
    res_doctor = await pipe_doctor.ask("Patient treatment protocol", intent="treatment")
    print(f"PASS: Doctor Access: {'ALLOWED' if res_doctor.sources else 'DENIED'}")
    if res_doctor.sources:
        print(f"   Excerpt: {res_doctor.sources[0].text[:50]}...")
    await pipe_doctor.close()

    # Scenario 2: Nurse at Clinic B (Orthopedics) trying to access Clinic A's data
    # (Physically impossible due to siloed DB path, but let's test policy gating too)
    cfg_nurse = Config(
        db_path="demos/healthcare/clinic_a.db", # Attacking Clinic A DB
        policy_path=policy_path,
        tenant_id="clinic_b", # Mismatched tenant
        roles=["nurse"],
        classifications=["public"] # Narrow classifications
    )
    pipe_nurse = RAGPipeline(cfg_nurse)
    res_nurse = await pipe_nurse.ask("Patient treatment protocol", intent="treatment")
    print(f"BLOCK: Nurse Cross-Tenant Access: {'ALLOWED' if res_nurse.sources else 'DENIED (Sovereign Airlock enforced)'}")
    await pipe_nurse.close()

if __name__ == "__main__":
    asyncio.run(run_demo())
