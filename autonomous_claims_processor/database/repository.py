"""
Database Repository Layer
=========================
CRUD operations and query helpers for all models.
"""
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, update, delete
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from .models import (
    Claim, Policy, ClaimDocument, AuditLog, 
    FraudRecord, Reserve, WeatherVerification
)


# ============================================================
# POLICY REPOSITORY
# ============================================================
class PolicyRepository:
    """Repository for Policy operations."""
    
    @staticmethod
    def get_by_policy_number(db: Session, policy_number: str) -> Optional[Policy]:
        """Fetch policy by policy number."""
        return db.query(Policy).filter(Policy.policy_number == policy_number).first()
    
    @staticmethod
    def get_by_id(db: Session, policy_id: uuid.UUID) -> Optional[Policy]:
        """Fetch policy by ID."""
        return db.query(Policy).filter(Policy.id == policy_id).first()
    
    @staticmethod
    def get_active_policies(db: Session, limit: int = 100) -> List[Policy]:
        """Get all active policies."""
        return db.query(Policy).filter(Policy.status == "ACTIVE").limit(limit).all()
    
    @staticmethod
    def create(db: Session, policy_data: Dict[str, Any]) -> Policy:
        """Create a new policy."""
        policy = Policy(**policy_data)
        db.add(policy)
        db.commit()
        db.refresh(policy)
        return policy
    
    @staticmethod
    def update_status(db: Session, policy_id: uuid.UUID, status: str) -> Optional[Policy]:
        """Update policy status."""
        db.query(Policy).filter(Policy.id == policy_id).update({"status": status})
        db.commit()
        return db.query(Policy).filter(Policy.id == policy_id).first()


# ============================================================
# CLAIM REPOSITORY
# ============================================================
class ClaimRepository:
    """Repository for Claim operations."""
    
    @staticmethod
    def get_by_claim_id(db: Session, claim_id: str) -> Optional[Claim]:
        """Fetch claim by claim ID."""
        return db.query(Claim).options(
            joinedload(Claim.policy),
            joinedload(Claim.documents)
        ).filter(Claim.claim_id == claim_id).first()
    
    @staticmethod
    def get_by_id(db: Session, claim_id: uuid.UUID) -> Optional[Claim]:
        """Fetch claim by UUID."""
        return db.query(Claim).options(
            joinedload(Claim.policy),
            joinedload(Claim.documents),
            joinedload(Claim.audit_logs)
        ).filter(Claim.id == claim_id).first()
    
    @staticmethod
    def get_claims_by_status(db: Session, status: str, limit: int = 50) -> List[Claim]:
        """Get claims by status."""
        return db.query(Claim).filter(Claim.status == status).limit(limit).all()
    
    @staticmethod
    def get_claims_by_adjuster(db: Session, adjuster_id: str, limit: int = 50) -> List[Claim]:
        """Get claims assigned to an adjuster."""
        return db.query(Claim).filter(
            Claim.assigned_adjuster_id == adjuster_id,
            Claim.status != "CLOSED"
        ).limit(limit).all()
    
    @staticmethod
    def get_high_fraud_risk_claims(db: Session, limit: int = 20) -> List[Claim]:
        """Get claims with high fraud risk."""
        return db.query(Claim).filter(
            Claim.fraud_risk_level.in_(["HIGH", "CRITICAL"])
        ).order_by(Claim.fraud_score.desc()).limit(limit).all()
    
    @staticmethod
    def create(db: Session, claim_data: Dict[str, Any]) -> Claim:
        """Create a new claim."""
        claim = Claim(**claim_data)
        db.add(claim)
        db.commit()
        db.refresh(claim)
        return claim
    
    @staticmethod
    def update(db: Session, claim_id: uuid.UUID, update_data: Dict[str, Any]) -> Optional[Claim]:
        """Update claim fields."""
        db.query(Claim).filter(Claim.id == claim_id).update(update_data)
        db.commit()
        return db.query(Claim).filter(Claim.id == claim_id).first()
    
    @staticmethod
    def update_status(db: Session, claim_id: uuid.UUID, status: str, 
                      current_stage: str = None) -> Optional[Claim]:
        """Update claim status and optionally current stage."""
        update_data = {"status": status}
        if current_stage:
            update_data["current_stage"] = current_stage
        return ClaimRepository.update(db, claim_id, update_data)
    
    @staticmethod
    def set_fraud_score(db: Session, claim_id: uuid.UUID, 
                        fraud_score: int, fraud_risk_level: str) -> Optional[Claim]:
        """Update fraud score and risk level."""
        return ClaimRepository.update(db, claim_id, {
            "fraud_score": fraud_score,
            "fraud_risk_level": fraud_risk_level
        })
    
    @staticmethod
    def set_coverage_status(db: Session, claim_id: uuid.UUID, 
                            coverage_status: str) -> Optional[Claim]:
        """Update coverage status."""
        return ClaimRepository.update(db, claim_id, {
            "coverage_status": coverage_status
        })
    
    @staticmethod
    def set_settlement(db: Session, claim_id: uuid.UUID, 
                       recommended_settlement: float,
                       ai_recommendation: str,
                       confidence: float) -> Optional[Claim]:
        """Update settlement recommendation."""
        return ClaimRepository.update(db, claim_id, {
            "recommended_settlement": recommended_settlement,
            "ai_recommendation": ai_recommendation,
            "recommendation_confidence": confidence
        })
    
    @staticmethod
    def complete_processing(db: Session, claim_id: uuid.UUID,
                            processing_end: datetime,
                            processing_time_seconds: int) -> Optional[Claim]:
        """Mark claim processing as complete."""
        return ClaimRepository.update(db, claim_id, {
            "processing_end": processing_end,
            "processing_time_seconds": processing_time_seconds
        })


# ============================================================
# CLAIM DOCUMENT REPOSITORY
# ============================================================
class ClaimDocumentRepository:
    """Repository for ClaimDocument operations."""
    
    @staticmethod
    def get_by_claim(db: Session, claim_id: uuid.UUID) -> List[ClaimDocument]:
        """Get all documents for a claim."""
        return db.query(ClaimDocument).filter(
            ClaimDocument.claim_id == claim_id
        ).all()
    
    @staticmethod
    def create(db: Session, document_data: Dict[str, Any]) -> ClaimDocument:
        """Create a new claim document."""
        doc = ClaimDocument(**document_data)
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc
    
    @staticmethod
    def update_ocr_data(db: Session, document_id: uuid.UUID,
                        ocr_text: str, ocr_confidence: float) -> Optional[ClaimDocument]:
        """Update OCR results for a document."""
        db.query(ClaimDocument).filter(
            ClaimDocument.id == document_id
        ).update({
            "ocr_text": ocr_text,
            "ocr_confidence": ocr_confidence,
            "ocr_completed": True,
            "processed_at": datetime.utcnow()
        })
        db.commit()
        return db.query(ClaimDocument).filter(ClaimDocument.id == document_id).first()
    
    @staticmethod
    def update_extraction(db: Session, document_id: uuid.UUID,
                          extraction_data: Dict[str, Any]) -> Optional[ClaimDocument]:
        """Update extracted data for a document."""
        db.query(ClaimDocument).filter(
            ClaimDocument.id == document_id
        ).update({
            "data_extracted": True,
            "extraction_data": extraction_data,
            "processed_at": datetime.utcnow()
        })
        db.commit()
        return db.query(ClaimDocument).filter(ClaimDocument.id == document_id).first()


# ============================================================
# AUDIT LOG REPOSITORY
# ============================================================
class AuditLogRepository:
    """Repository for AuditLog operations."""
    
    @staticmethod
    def get_by_claim(db: Session, claim_id: uuid.UUID, limit: int = 100) -> List[AuditLog]:
        """Get all audit logs for a claim (ordered by timestamp)."""
        return db.query(AuditLog).filter(
            AuditLog.claim_id == claim_id
        ).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    @staticmethod
    def create(db: Session, audit_data: Dict[str, Any]) -> AuditLog:
        """Create a new audit log entry."""
        audit = AuditLog(**audit_data)
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
    
    @staticmethod
    def log_agent_action(db: Session, claim_id: uuid.UUID, agent_name: str,
                         action_detail: str, data_sources: List[str],
                         rationale: str, confidence: float) -> AuditLog:
        """Log an AI agent action."""
        return AuditLogRepository.create(db, {
            "claim_id": claim_id,
            "action_type": "AGENT_ACTION",
            "actor": agent_name,
            "actor_type": "AI_AGENT",
            "action_detail": action_detail,
            "data_sources_used": data_sources,
            "decision_rationale": rationale,
            "confidence_score": confidence
        })
    
    @staticmethod
    def log_decision(db: Session, claim_id: uuid.UUID, actor: str,
                     decision_type: str, previous_value: Dict,
                     new_value: Dict, rationale: str) -> AuditLog:
        """Log a decision made on a claim."""
        return AuditLogRepository.create(db, {
            "claim_id": claim_id,
            "action_type": "DECISION",
            "actor": actor,
            "actor_type": "AI_AGENT" if actor.endswith("Agent") else "HUMAN_ADJUSTER",
            "action_detail": decision_type,
            "previous_value": previous_value,
            "new_value": new_value,
            "decision_rationale": rationale
        })


# ============================================================
# FRAUD RECORD REPOSITORY
# ============================================================
class FraudRecordRepository:
    """Repository for FraudRecord operations."""
    
    @staticmethod
    def get_by_claim(db: Session, claim_id: uuid.UUID) -> Optional[FraudRecord]:
        """Get fraud record for a claim."""
        return db.query(FraudRecord).filter(
            FraudRecord.claim_id == claim_id
        ).first()
    
    @staticmethod
    def create(db: Session, fraud_data: Dict[str, Any]) -> FraudRecord:
        """Create a new fraud record."""
        record = FraudRecord(**fraud_data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    
    @staticmethod
    def update_siu_referral(db: Session, claim_id: uuid.UUID,
                            siu_referred: bool, justification: str = None) -> Optional[FraudRecord]:
        """Update SIU referral status."""
        update_data = {
            "siu_referred_at": datetime.utcnow() if siu_referred else None
        }
        if justification:
            update_data["siu_referral_justification"] = justification
        
        db.query(FraudRecord).filter(
            FraudRecord.claim_id == claim_id
        ).update(update_data)
        db.commit()
        return db.query(FraudRecord).filter(FraudRecord.claim_id == claim_id).first()


# ============================================================
# RESERVE REPOSITORY
# ============================================================
class ReserveRepository:
    """Repository for Reserve operations."""
    
    @staticmethod
    def get_by_claim(db: Session, claim_id: uuid.UUID) -> List[Reserve]:
        """Get all reserves for a claim."""
        return db.query(Reserve).filter(
            Reserve.claim_id == claim_id
        ).order_by(Reserve.created_at.desc()).all()
    
    @staticmethod
    def get_current_reserve(db: Session, claim_id: uuid.UUID) -> Optional[Reserve]:
        """Get the most recent reserve for a claim."""
        return db.query(Reserve).filter(
            Reserve.claim_id == claim_id
        ).order_by(Reserve.created_at.desc()).first()
    
    @staticmethod
    def create(db: Session, reserve_data: Dict[str, Any]) -> Reserve:
        """Create a new reserve entry."""
        reserve = Reserve(**reserve_data)
        db.add(reserve)
        db.commit()
        db.refresh(reserve)
        return reserve
    
    @staticmethod
    def set_initial_reserve(db: Session, claim_id: uuid.UUID,
                            case_reserve: float, reason: str,
                            adjuster_id: str = "SYSTEM") -> Reserve:
        """Set initial reserve for a claim."""
        alae_reserve = case_reserve * 0.10  # 10% ALAE default
        return ReserveRepository.create(db, {
            "claim_id": claim_id,
            "case_reserve": case_reserve,
            "alae_reserve": alae_reserve,
            "total_reserve": case_reserve + alae_reserve,
            "reserve_type": "INITIAL",
            "reason": reason,
            "adjuster_id": adjuster_id
        })


# ============================================================
# WEATHER VERIFICATION REPOSITORY
# ============================================================
class WeatherVerificationRepository:
    """Repository for WeatherVerification operations."""
    
    @staticmethod
    def get_by_claim(db: Session, claim_id: uuid.UUID) -> Optional[WeatherVerification]:
        """Get weather verification for a claim."""
        return db.query(WeatherVerification).filter(
            WeatherVerification.claim_id == claim_id
        ).first()
    
    @staticmethod
    def create(db: Session, weather_data: Dict[str, Any]) -> WeatherVerification:
        """Create a new weather verification record."""
        verification = WeatherVerification(**weather_data)
        db.add(verification)
        db.commit()
        db.refresh(verification)
        return verification
