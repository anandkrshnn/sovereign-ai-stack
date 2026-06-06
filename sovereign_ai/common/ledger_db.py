import asyncio
import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, Integer, String, select
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.ext.declarative import declarative_base

from .hardware_trust import SecureAnchor, SoftwareSimulatorAnchor
from .merkle import MerkleTree

Base = declarative_base()


class AuditLedgerRecord(Base):
    __tablename__ = "audit_ledger"

    sequence_number = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    event_data = Column(JSON, nullable=False)

    prev_hash = Column(String(64), nullable=False)
    curr_hash = Column(
        String(64), nullable=False, index=True
    )  # Indexed for O(1) Merkle proof lookups

    signature = Column(String, nullable=False)  # Base64
    public_key = Column(String, nullable=True)  # Base64

    # Merkle Block tracking
    checkpoint_seq = Column(
        Integer, nullable=True, index=True
    )  # If this record was sealed in a checkpoint


class DatabaseAuditChain:
    """
    O(1) Merkle Ledger backend using SQLAlchemy async core.
    Compatible with PostgreSQL (asyncpg) and SQLite (aiosqlite).
    """

    def __init__(self, tenant_id: str, database_uri: str, anchor: Optional[SecureAnchor] = None):
        self.tenant_id = tenant_id
        self.database_uri = database_uri
        self.engine = create_async_engine(self.database_uri, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

        self.anchor = anchor or SoftwareSimulatorAnchor(tenant_id)

        self.checkpoint_interval = 10
        self._last_hash = "0" * 64

    async def initialize(self):
        """Creates tables if they don't exist and initializes the state."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with self.async_session() as session:
            # Load last hash
            result = await session.execute(
                select(AuditLedgerRecord.curr_hash)
                .where(AuditLedgerRecord.tenant_id == self.tenant_id)
                .order_by(AuditLedgerRecord.sequence_number.desc())
                .limit(1)
            )
            row = result.first()
            if row:
                self._last_hash = row[0]
            else:
                self._last_hash = "0" * 64

    def _canonical_json(self, record_dict: Dict[str, Any]) -> bytes:
        return json.dumps(record_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")

    async def append_record(self, action: str, data: Dict[str, Any]) -> int:
        """Appends a new record to the database ledger and returns its sequence number."""
        async with self.async_session() as session:
            async with session.begin():
                record_dict = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": action,
                    "tenant_id": self.tenant_id,
                    "event_data": data,
                    "prev_hash": self._last_hash,
                }

                # Sign
                canonical = self._canonical_json(record_dict)
                signature_bytes = await asyncio.to_thread(self.anchor.sign, canonical)
                record_dict["signature"] = base64.b64encode(signature_bytes).decode("utf-8")

                pub_key = self.anchor.get_public_key()
                if pub_key:
                    from cryptography.hazmat.primitives import serialization

                    from .schemas import SigningAlgorithm

                    pub_bytes = pub_key.public_bytes(
                        encoding=(
                            serialization.Encoding.Raw
                            if self.anchor.algorithm == SigningAlgorithm.ED25519
                            else serialization.Encoding.X962
                        ),
                        format=(
                            serialization.PublicFormat.Raw
                            if self.anchor.algorithm == SigningAlgorithm.ED25519
                            else serialization.PublicFormat.UncompressedPoint
                        ),
                    )
                    record_dict["public_key"] = base64.b64encode(pub_bytes).decode("utf-8")

                # Hash (Chain Link)
                hash_canonical = self._canonical_json(record_dict)
                curr_hash = hashlib.sha256(hash_canonical).hexdigest()
                self._last_hash = curr_hash

                db_record = AuditLedgerRecord(
                    tenant_id=self.tenant_id,
                    timestamp=record_dict["timestamp"],
                    action=action,
                    event_data=data,
                    prev_hash=record_dict["prev_hash"],
                    curr_hash=curr_hash,
                    signature=record_dict["signature"],
                    public_key=record_dict.get("public_key"),
                )
                session.add(db_record)
                await session.flush()

                seq_num = db_record.sequence_number

                # Simple periodic checkpointing logic (for demo/minimalism)
                if seq_num % self.checkpoint_interval == 0:
                    await self._create_checkpoint(session, seq_num)

                return seq_num

    async def _create_checkpoint(self, session: AsyncSession, current_seq: int):
        """Seals the previous block with a Merkle Root checkpoint."""
        start_seq = max(1, current_seq - self.checkpoint_interval + 1)
        result = await session.execute(
            select(AuditLedgerRecord)
            .where(AuditLedgerRecord.tenant_id == self.tenant_id)
            .where(AuditLedgerRecord.sequence_number.between(start_seq, current_seq))
            .order_by(AuditLedgerRecord.sequence_number.asc())
        )
        records = result.scalars().all()

        hashes = [r.curr_hash for r in records]
        tree = MerkleTree(hashes)
        root = tree.root

        quote = await asyncio.to_thread(self.anchor.generate_quote, root, [0, 11])

        # Log checkpoint
        checkpoint_data = {
            "merkle_root": root,
            "start_seq": start_seq,
            "end_seq": current_seq,
            "attestation_quote": quote.model_dump() if quote else None,
        }

        # We recursively call append_record logic manually to avoid breaking transaction
        record_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "MERKLE_CHECKPOINT",
            "tenant_id": self.tenant_id,
            "event_data": checkpoint_data,
            "prev_hash": self._last_hash,
        }
        canonical = self._canonical_json(record_dict)
        signature_bytes = await asyncio.to_thread(self.anchor.sign, canonical)
        record_dict["signature"] = base64.b64encode(signature_bytes).decode("utf-8")
        hash_canonical = self._canonical_json(record_dict)
        curr_hash = hashlib.sha256(hash_canonical).hexdigest()
        self._last_hash = curr_hash

        chkpt = AuditLedgerRecord(
            tenant_id=self.tenant_id,
            timestamp=record_dict["timestamp"],
            action="MERKLE_CHECKPOINT",
            event_data=checkpoint_data,
            prev_hash=record_dict["prev_hash"],
            curr_hash=curr_hash,
            signature=record_dict["signature"],
        )
        session.add(chkpt)
        await session.flush()

        # Mark records as sealed
        for r in records:
            r.checkpoint_seq = chkpt.sequence_number

    async def get_audit_proof(self, audit_id: int) -> Dict[str, Any]:
        """O(1) lookup of Merkle Proof using indexed checkpoint_seq."""
        async with self.async_session() as session:
            # Find the record
            result = await session.execute(
                select(AuditLedgerRecord)
                .where(AuditLedgerRecord.sequence_number == audit_id)
                .where(AuditLedgerRecord.tenant_id == self.tenant_id)
            )
            target = result.scalar_one_or_none()
            if not target:
                raise ValueError(f"Audit ID {audit_id} not found.")

            if not target.checkpoint_seq:
                # Force a checkpoint to seal this record for the demo
                await self._create_checkpoint(session, target.sequence_number)
                await session.commit()
                # Reload target
                result = await session.execute(
                    select(AuditLedgerRecord).where(AuditLedgerRecord.sequence_number == audit_id)
                )
                target = result.scalar_one()

            # Load the checkpoint
            result = await session.execute(
                select(AuditLedgerRecord).where(
                    AuditLedgerRecord.sequence_number == target.checkpoint_seq
                )
            )
            chkpt = result.scalar_one()

            # Load the block
            start_seq = chkpt.event_data["start_seq"]
            end_seq = chkpt.event_data["end_seq"]
            result = await session.execute(
                select(AuditLedgerRecord)
                .where(AuditLedgerRecord.tenant_id == self.tenant_id)
                .where(AuditLedgerRecord.sequence_number.between(start_seq, end_seq))
                .order_by(AuditLedgerRecord.sequence_number.asc())
            )
            block = result.scalars().all()

            hashes = [r.curr_hash for r in block]
            tree = MerkleTree(hashes)
            index = [r.sequence_number for r in block].index(audit_id)

            return {
                "leaf_hash": target.curr_hash,
                "root_hash": chkpt.event_data["merkle_root"],
                "proof": tree.get_proof(index),
                "attestation_quote": chkpt.event_data.get("attestation_quote"),
            }

    async def verify_chain(self) -> bool:
        # Simplified verification logic: scan DB and re-hash.
        # In a real system, you page through it.
        async with self.async_session() as session:
            result = await session.execute(
                select(AuditLedgerRecord)
                .where(AuditLedgerRecord.tenant_id == self.tenant_id)
                .order_by(AuditLedgerRecord.sequence_number.asc())
            )
            records = result.scalars().all()

            prev_hash = "0" * 64
            for r in records:
                if r.prev_hash != prev_hash:
                    return False
                record_dict = {
                    "timestamp": r.timestamp,
                    "action": r.action,
                    "tenant_id": r.tenant_id,
                    "event_data": r.event_data,
                    "prev_hash": r.prev_hash,
                    "signature": r.signature,
                }
                if r.public_key:
                    record_dict["public_key"] = r.public_key
                canonical = self._canonical_json(record_dict)
                recalc_hash = hashlib.sha256(canonical).hexdigest()
                if recalc_hash != r.curr_hash:
                    return False
                prev_hash = recalc_hash
            return True
