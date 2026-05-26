"""
SQLAlchemy ORM Models for Insurance Claims Processor
=====================================================
Tables: claims, policies, claim_documents, audit_logs, fraud_records, reserves
"""
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, 
    ForeignKey, JSON, Numeric, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .connection import Base


def generate_uuid():
    return str(uuid.uuid4())


# ============================================================
# POLICY MODEL
# ============================================================
class Policy(Base):
    """
    Insurance Policy records.
    Stores policy details, coverage limits, endorsements.
    """
    __tablename__ = "policies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    policy_number = Column(String(50), unique=True, nullable=False, index=True)
    policy_form = Column(String(100))  # ISO form number
    policy_type = Column(String(50))  # Auto, Property, Health, Liability
    
    # Policy holder info
    policyholder_name = Column(String(200), nullable=False)
    policyholder_dob = Column(DateTime)
    policyholder_address = Column(Text)
    policyholder_phone = Column(String(20))
    policyholder_email = Column(String(100))
    
    # Policy period
    effective_date = Column(DateTime, nullable=False)
    expiration_date = Column(DateTime, nullable=False)
    
    # Coverage details
    coverage_a_limit = Column(Numeric(12, 2))  # Dwelling / Primary
    coverage_b_limit = Column(Numeric(12, 2))  # Other Structures
    coverage_c_limit = Column(Numeric(12, 2))  # Personal Property
    coverage_d_limit = Column(Numeric(12, 2))  # Loss of Use
    medical_payments_limit = Column(Numeric(12, 2))
    
    # Deductibles
    all_peril_deductible = Column(Numeric(10, 2))
    wind_hail_deductible = Column(Numeric(10, 2))
    hurricane_deductible_percent = Column(Float)
    
    # Policy status
    status = Column(String(20), default="ACTIVE")  # ACTIVE, LAPSED, CANCELLED, EXPIRED
    state_of_issue = Column(String(2))
    
    # Endorsements (stored as JSON)
    endorsements = Column(JSONB, default=list)
    
    # Vector embedding for RAG (Pinecone sync)
    policy_embedding_id = Column(String(100))  # Pinecone vector ID
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    claims = relationship("Claim", back_populates="policy", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_policy_status', 'status'),
        Index('ix_policy_dates', 'effective_date', 'expiration_date'),
    )
    
    def __repr__(self):
        return f"<Policy(policy_number='{self.policy_number}', status='{self.status}')>"


# ============================================================
# CLAIM MODEL
# ============================================================
class Claim(Base):
    """
    Insurance Claim records.
    Main claim tracking table with all claim-level data.
    """
    __tablename__ = "claims"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    claim_id = Column(String(50), unique=True, nullable=False, index=True)  # Human-readable ID
    
    # Foreign key to policy
    policy_id = Column(UUID(as_uuid=True), ForeignKey('policies.id'), nullable=False)
    policy = relationship("Policy", back_populates="claims")
    
    # Claim type
    claim_type = Column(String(50))  # auto, property, health, liability
    peril_type = Column(String(100))  # fire, theft, wind, collision, etc.
    
    # Dates
    date_of_loss = Column(DateTime, nullable=False)
    fnol_received = Column(DateTime, nullable=False)  # First Notice of Loss
    reported_date = Column(DateTime)
    
    # Claimant info (may differ from policyholder)
    claimant_name = Column(String(200))
    claimant_phone = Column(String(20))
    claimant_email = Column(String(100))
    claimant_address = Column(Text)
    
    # Loss details
    loss_location = Column(Text)
    loss_description = Column(Text)
    loss_coordinates_lat = Column(Float)  # GPS for weather verification
    loss_coordinates_lng = Column(Float)
    
    # Financials
    claimed_amount = Column(Numeric(12, 2))
    initial_reserve = Column(Numeric(12, 2))
    current_reserve = Column(Numeric(12, 2))
    paid_amount = Column(Numeric(12, 2), default=0)
    
    # Classification
    severity = Column(String(20))  # CAT, LARGE, STANDARD, SMALL
    complexity = Column(String(20))  # COMPLEX, STANDARD, SIMPLE
    
    # Pipeline status
    pipeline_type = Column(String(20))  # fast_track, standard, complex, cat
    current_stage = Column(String(50), default="INTAKE")  # INTAKE, FRAUD_CHECK, COVERAGE, etc.
    status = Column(String(30), default="OPEN")  # OPEN, IN_PROGRESS, PENDING_INFO, CLOSED, DENIED
    
    # Fraud indicators
    fraud_score = Column(Integer, default=0)
    fraud_risk_level = Column(String(20))  # LOW, MEDIUM, HIGH, CRITICAL
    siu_referral = Column(Boolean, default=False)
    
    # Coverage determination
    coverage_status = Column(String(30))  # COVERED, PARTIALLY_COVERED, NOT_COVERED, UNDER_REVIEW
    
    # Settlement
    recommended_settlement = Column(Numeric(12, 2))
    actual_settlement = Column(Numeric(12, 2))
    ai_recommendation = Column(String(50))  # APPROVE, DENY, PARTIAL, REFER_TO_ADJUSTER
    recommendation_confidence = Column(Float)
    
    # Human assignment
    requires_human_adjuster = Column(Boolean, default=True)
    assigned_adjuster_id = Column(String(50))
    assigned_adjuster_name = Column(String(200))
    
    # Processing metadata
    processing_start = Column(DateTime)
    processing_end = Column(DateTime)
    processing_time_seconds = Column(Integer)
    
    # Disclaimer (mandatory)
    mandatory_disclaimer = Column(Text, default="REQUIRES LICENSED ADJUSTER REVIEW AND AUTHORIZATION BEFORE EXECUTION")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    documents = relationship("ClaimDocument", back_populates="claim", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="claim", cascade="all, delete-orphan")
    fraud_records = relationship("FraudRecord", back_populates="claim", cascade="all, delete-orphan")
    reserves = relationship("Reserve", back_populates="claim", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_claim_status', 'status'),
        Index('ix_claim_fnol', 'fnol_received'),
        Index('ix_claim_loss_date', 'date_of_loss'),
        Index('ix_claim_fraud', 'fraud_risk_level'),
    )
    
    def __repr__(self):
        return f"<Claim(claim_id='{self.claim_id}', status='{self.status}')>"


# ============================================================
# CLAIM DOCUMENT MODEL
# ============================================================
class ClaimDocument(Base):
    """
    Documents associated with a claim.
    PDFs, images, emails, transcripts, etc.
    """
    __tablename__ = "claim_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    claim_id = Column(UUID(as_uuid=True), ForeignKey('claims.id'), nullable=False)
    claim = relationship("Claim", back_populates="documents")
    
    # Document metadata
    document_type = Column(String(50))  # claim_form, photo, police_report, medical_record, estimate
    file_name = Column(String(255))
    file_format = Column(String(20))  # PDF, JPG, PNG, TXT, EMAIL
    file_size_bytes = Column(Integer)
    file_path = Column(Text)  # S3 or local storage path
    
    # OCR data
    ocr_text = Column(Text)
    ocr_confidence = Column(Float)
    ocr_completed = Column(Boolean, default=False)
    
    # Extraction status
    data_extracted = Column(Boolean, default=False)
    extraction_data = Column(JSONB, default=dict)  # Structured data from doc
    
    # Quality flags
    quality_score = Column(String(20))  # good, fair, poor
    metadata_anomalies = Column(JSONB, default=list)  # EXIF issues, etc.
    
    # Timestamps
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    
    __table_args__ = (
        Index('ix_doc_claim', 'claim_id'),
        Index('ix_doc_type', 'document_type'),
    )
    
    def __repr__(self):
        return f"<ClaimDocument(document_type='{self.document_type}', file_name='{self.file_name}')>"


# ============================================================
# AUDIT LOG MODEL
# ============================================================
class AuditLog(Base):
    """
    Immutable audit trail for compliance.
    Every action on every claim is logged here.
    """
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    claim_id = Column(UUID(as_uuid=True), ForeignKey('claims.id'), nullable=False)
    claim = relationship("Claim", back_populates="audit_logs")
    
    # Action details
    action_type = Column(String(100), nullable=False)  # AGENT_ACTION, DECISION, COMMUNICATION, PAYMENT, etc.
    actor = Column(String(100), nullable=False)  # agent_name, adjuster_id, system
    actor_type = Column(String(50))  # AI_AGENT, HUMAN_ADJUSTER, SYSTEM
    
    # Action data
    action_detail = Column(Text)
    data_sources_used = Column(JSONB, default=list)
    decision_rationale = Column(Text)
    confidence_score = Column(Float)
    
    # Previous and new values (for tracking changes)
    previous_value = Column(JSONB)
    new_value = Column(JSONB)
    
    # Immutability
    record_hash = Column(String(64), index=True)  # SHA-256 hash for integrity
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_audit_claim', 'claim_id'),
        Index('ix_audit_timestamp', 'timestamp'),
        Index('ix_audit_actor', 'actor'),
    )
    
    def __repr__(self):
        return f"<AuditLog(claim_id='{self.claim_id}', action='{self.action_type}')>"


# ============================================================
# FRAUD RECORD MODEL
# ============================================================
class FraudRecord(Base):
    """
    Fraud detection results and history.
    Tracks red flags, ML scores, SIU referrals.
    """
    __tablename__ = "fraud_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    claim_id = Column(UUID(as_uuid=True), ForeignKey('claims.id'), nullable=False)
    claim = relationship("Claim", back_populates="fraud_records")
    
    # ML Scores
    isolation_forest_score = Column(Float)
    xgboost_fraud_probability = Column(Float)
    graph_network_score = Column(Float)
    composite_fraud_score = Column(Integer)
    
    # Risk assessment
    fraud_risk_level = Column(String(20))  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Red flags detected (stored as JSON)
    red_flags = Column(JSONB, default=list)
    # Format: [{"flag_id": "", "category": "", "description": "", "severity": ""}]
    
    # Historical matches
    historical_similar_claims = Column(JSONB, default=list)
    
    # ISO ClaimSearch results
    iso_results = Column(JSONB, default=dict)
    prior_claims_count = Column(Integer, default=0)
    prior_fraud_history = Column(Boolean, default=False)
    
    # Network analysis
    network_connections = Column(JSONB, default=list)  # Fraud ring detection
    
    # Actions taken
    recommendation = Column(String(50))  # STANDARD_PROCESS, ENHANCED_REVIEW, SIU_REFERRAL, CLAIM_HOLD
    siu_referral_justification = Column(Text)
    siu_referred_at = Column(DateTime(timezone=True))
    siu_investigator_id = Column(String(50))
    siu_findings = Column(Text)
    siu_status = Column(String(30))  # PENDING, IN_PROGRESS, CLOSED_NO_FRAUD, FRAUD_CONFIRMED
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('ix_fraud_claim', 'claim_id'),
        Index('ix_fraud_score', 'composite_fraud_score'),
        Index('ix_fraud_risk', 'fraud_risk_level'),
    )
    
    def __repr__(self):
        return f"<FraudRecord(claim_id='{self.claim_id}', score={self.composite_fraud_score})>"


# ============================================================
# RESERVE MODEL
# ============================================================
class Reserve(Base):
    """
    Claim reserve tracking.
    Tracks initial and adjusted reserves over claim lifecycle.
    """
    __tablename__ = "reserves"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    claim_id = Column(UUID(as_uuid=True), ForeignKey('claims.id'), nullable=False)
    claim = relationship("Claim", back_populates="reserves")
    
    # Reserve amounts
    case_reserve = Column(Numeric(12, 2), nullable=False)
    alae_reserve = Column(Numeric(12, 2), default=0)  # Allocated Loss Adjustment Expense
    total_reserve = Column(Numeric(12, 2), nullable=False)
    
    # Reserve type
    reserve_type = Column(String(30))  # INITIAL, SUPPLEMENTAL, REDUCTION, CLOSING
    
    # Reason for reserve/change
    reason = Column(Text)
    
    # Adjuster who set/changed reserve
    adjuster_id = Column(String(50))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('ix_reserve_claim', 'claim_id'),
    )
    
    def __repr__(self):
        return f"<Reserve(claim_id='{self.claim_id}', total={self.total_reserve})>"


# ============================================================
# WEATHER VERIFICATION MODEL
# ============================================================
class WeatherVerification(Base):
    """
    Weather data verification results.
    Stores weather API responses for claims.
    """
    __tablename__ = "weather_verifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    claim_id = Column(UUID(as_uuid=True), ForeignKey('claims.id'), nullable=False)
    claim = relationship("Claim")
    
    # Loss details
    loss_location = Column(Text)
    loss_date = Column(DateTime, nullable=False)
    reported_cause = Column(String(100))
    
    # Weather data
    temperature_f = Column(Float)
    wind_speed_mph = Column(Float)
    wind_gust_mph = Column(Float)
    precipitation_inches = Column(Float)
    hail_recorded = Column(Boolean, default=False)
    hail_size_inches = Column(Float)
    severe_weather_alert = Column(Boolean, default=False)
    alert_type = Column(String(100))
    lightning_strikes_nearby = Column(Boolean, default=False)
    flood_advisory = Column(Boolean, default=False)
    
    # Data sources
    sources_queried = Column(JSONB, default=list)
    data_confidence = Column(String(20))  # HIGH, MEDIUM, LOW
    
    # Verification result
    verdict = Column(String(30))  # CONFIRMED, PARTIALLY_CONFIRMED, INCONSISTENT, INCONCLUSIVE, NOT_APPLICABLE
    verdict_detail = Column(Text)
    
    # Photo analysis
    photos_analyzed = Column(Integer, default=0)
    photo_date_consistent = Column(Boolean, default=True)
    photo_location_consistent = Column(Boolean, default=True)
    
    # Fraud signal
    fraud_signal = Column(Boolean, default=False)
    fraud_signal_reason = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('ix_weather_claim', 'claim_id'),
    )
    
    def __repr__(self):
        return f"<WeatherVerification(claim_id='{self.claim_id}', verdict='{self.verdict}')>"
