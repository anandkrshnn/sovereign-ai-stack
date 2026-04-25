import asyncio
import os
from local_rag import RAGPipeline, Config
from local_rag.schemas import Document

# Get the directory of the current script
base_dir = os.path.dirname(os.path.abspath(__file__))

async def setup_healthcare():
    print("[Healthcare] Setting up Data...")
    # Clinic A: Cardiology
    cfg_a = Config(db_path=os.path.join(base_dir, "healthcare", "clinic_a.db"), tenant_id="clinic_a")
    pipe_a = RAGPipeline(cfg_a)
    await pipe_a.ingest([
        Document(doc_id="PROTOCOL-1", source="EHR", 
                 content="Patient_X Treatment Protocol: Diagnosis=Hypertension. Rx: Lisinopril 10mg daily. Follow-up 4 weeks.", 
                 tenant_id="clinic_a", metadata={"classification": "PHI", "department": "cardiology"}),
        Document(doc_id="TREND-2026", source="Analytics", 
                 content="De-identified Cardiology Trends Q1 2026: 15% increase in hypertension reports across demographic age 45-60.", 
                 tenant_id="clinic_a", metadata={"classification": "public", "department": "cardiology"}),
        Document(doc_id="HOURS", source="Admin", 
                 content="Clinic A Hours: Monday-Friday 9am-5pm. Closed weekends.", 
                 tenant_id="clinic_a", metadata={"classification": "public"})
    ])
    await pipe_a.close()

    # Clinic B: Orthopedics (Isolated)
    cfg_b = Config(db_path=os.path.join(base_dir, "healthcare", "clinic_b.db"), tenant_id="clinic_b")
    pipe_b = RAGPipeline(cfg_b)
    await pipe_b.ingest([
        Document(doc_id="SURGERY-1", source="EHR", 
                 content="Patient_Y Knee Surgery Roadmap: Post-op physio 3x/week for 12 weeks.", 
                 tenant_id="clinic_b", metadata={"classification": "PHI", "department": "orthopedics"})
    ])
    await pipe_b.close()

async def setup_finance():
    print("[Finance] Setting up Data...")
    cfg = Config(db_path=os.path.join(base_dir, "finance", "finance.db"), tenant_id="acme_corp")
    pipe = RAGPipeline(cfg)
    await pipe.ingest([
        Document(doc_id="REV-Q2", source="Internal", 
                 content="Q2 Revenue Breakdown: APAC: $12.4M | EMEA: $8.7M | Americas: $21.5M. Growth: +8% YoY.", 
                 tenant_id="acme_corp", metadata={"classification": "confidential"}),
        Document(doc_id="STRIPE-CRED", source="Vault", 
                 content="Stripe Integration Keys: Primary Key='sk_live_51P2FAKEKEY'. Primary Secret='rk_live_99XYZ'.", 
                 tenant_id="acme_corp", metadata={"classification": "restricted"}),
        Document(doc_id="AUDIT-Q2", source="Compliance", 
                 content="Q2 Revenue Audit Trail: Verified by External Auditor on 2026-04-10. All entries balanced.", 
                 tenant_id="acme_corp", metadata={"classification": "public"})
    ])
    await pipe.close()

async def setup_engineering():
    print("[Engineering] Setting up Data...")
    cfg = Config(db_path=os.path.join(base_dir, "engineering", "eng.db"), tenant_id="eng_team")
    pipe = RAGPipeline(cfg)
    await pipe.ingest([
        Document(doc_id="K8S-CONFIG", source="Git", 
                 content="Production Kubernetes Config: image: myapp:v1.2.3 | replicas: 3 | resources: limit-cpu: '2'.", 
                 tenant_id="eng_team", metadata={"classification": "internal"}),
        Document(doc_id="AWS-CRED", source="Vault", 
                 content="AWS Prod Credentials: access_key: 'AKIA_PROD_123' | secret_access_key: 'EXAMPLE_SECRET_KEY'.", 
                 tenant_id="eng_team", metadata={"classification": "internal"}),
        Document(doc_id="STAGING-GUIDE", source="Docs", 
                 content="Staging Deployment Guide: use namespace 'staging-apps'. Run 'helm upgrade' with values-staging.yaml.", 
                 tenant_id="eng_team", metadata={"classification": "public"})
    ])
    await pipe.close()

async def main():
    await setup_healthcare()
    await setup_finance()
    await setup_engineering()
    print("\nSUCCESS: Hybrid RAG + Security demo data populated.")

if __name__ == "__main__":
    asyncio.run(main())
