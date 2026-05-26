"""
Pydantic Schemas for API Request/Response Validation
=====================================================
All API input/output models with validation.
"""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================
# ENUMS
# ============================================================

class ClaimType(str, Enum):
    AUTO = "auto"
    PROPERTY = "property"
    HEALTH = "health"
    LIABILITY = "liability"
    OTHER = "other"


class ClaimStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_INFO = "PENDING_INFO"
    CLOSED = "CLOSED"
    DENIED = "DENIED"


class Severity(str, Enum):
    CAT = "CAT"
    LARGE = "LARGE"
    STANDARD = "STANDARD"
    SMALL = "SMALL"


class Complexity(str, Enum):
    COMPLEX = "COMPLEX"
    STANDARD = "STANDARD"
    SIMPLE = "SIMPLE"


class FraudRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CoverageStatus(str, Enum):
    COVERED = "COVERED"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    NOT_COVERED = "NOT_COVERED"
    UNDER_REVIEW = "UNDER_REVIEW"


class AIRecommendation(str, Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"
    PARTIAL = "PARTIAL"
    REFER_TO_ADJUSTER = "REFER_TO_ADJUSTER"


class PipelineType(str, Enum):
    FAST_TRACK = "fast_track"
    STANDARD = "standard"
    COMPLEX = "complex"
    CAT = "cat"


class PipelineStage(str, Enum):
    INTAKE = "INTAKE"
    FRAUD_CHECK = "FRAUD_CHECK"
    COVERAGE_CHECK = "COVERAGE_CHECK"
    WEATHER_VERIFICATION = "WEATHER_VERIFICATION"
    PAYOUT_CALCULATION = "PAYOUT_CALCULATION"
    AUDIT = "AUDIT"
    COMPLETED = "COMPLETED"


# ============================================================
# POLICY SCHEMAS
# ============================================================

class PolicyBase(BaseModel):
    policy_number: str = Field(..., min_length=1, max_length=50)
    policy_form: Optional[str] = None
    policy_type: str = Field(..., min_length=1)
    policyholder_name: str = Field(..., min_length=1, max_length=200)
    policyholder_dob: Optional[datetime] = None
    policyholder_address: Optional[str] = None
    policyholder_phone: Optional[str] = None
    policyholder_email: Optional[EmailStr] = None
    effective_date: datetime
    expiration_date: datetime
    coverage_a_limit: Optional[float] = None
    coverage_b_limit: Optional[float] = None
    coverage_c_limit: Optional[float] = None
    coverage_d_limit: Optional[float] = None
    medical_payments_limit: Optional[float] = None
    all_peril_deductible: Optional[float] = None
    wind_hail_deductible: Optional[float] = None
    hurricane_deductible_percent: Optional[float] = None
    status: str = "ACTIVE"
    state_of_issue: str = Field(..., min_length=2, max_length=2)


class PolicyCreate(PolicyBase):
    """Schema for creating a new policy."""
    pass


class PolicyResponse(PolicyBase):
    """Schema for policy response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None


# ============================================================
# CLAIM SCHEMAS
# ============================================================

class ClaimantInfo(BaseModel):
    """Claimant information."""
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None


class LossInfo(BaseModel):
    """Loss information."""
    date_of_loss: datetime
    time_of_loss: Optional[datetime] = None
    location: str
    description: str
    cause_of_loss: str
    coordinates_lat: Optional[float] = None
    coordinates_lng: Optional[float] = None


class DamageInfo(BaseModel):
    """Damage information."""
    items: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_amount: Optional[float] = None
    photos_submitted: int = 0
    police_report_number: Optional[str] = None


class ClaimCreate(BaseModel):
    """Schema for creating a new claim."""
    policy_number: str = Field(..., description="Policy number for this claim")
    claim_type: ClaimType
    peril_type: str
    claimant: ClaimantInfo
    loss: LossInfo
    damage: Optional[DamageInfo] = None
    claimed_amount: Optional[float] = None
    documents: Optional[List[Dict[str, Any]]] = None


class ClaimResponse(BaseModel):
    """Schema for claim response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    claim_id: str
    policy_id: str
    policy_number: str
    claim_type: str
    peril_type: str
    date_of_loss: datetime
    fnol_received: datetime
    claimant_name: str
    loss_location: str
    loss_description: str
    claimed_amount: Optional[float] = None
    initial_reserve: Optional[float] = None
    current_reserve: Optional[float] = None
    paid_amount: Optional[float] = 0
    severity: Optional[str] = None
    complexity: Optional[str] = None
    pipeline_type: Optional[str] = None
    current_stage: str
    status: str
    fraud_score: int = 0
    fraud_risk_level: Optional[str] = None
    siu_referral: bool = False
    coverage_status: Optional[str] = None
    recommended_settlement: Optional[float] = None
    ai_recommendation: Optional[str] = None
    recommendation_confidence: Optional[float] = None
    requires_human_adjuster: bool = True
    assigned_adjuster_id: Optional[str] = None
    assigned_adjuster_name: Optional[str] = None
    processing_start: Optional[datetime] = None
    processing_end: Optional[datetime] = None
    processing_time_seconds: Optional[int] = None
    mandatory_disclaimer: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class ClaimSummary(BaseModel):
    """Summary view of a claim for listings."""
    claim_id: str
    policy_number: str
    claimant_name: str
    claim_type: str
    date_of_loss: datetime
    claimed_amount: Optional[float] = None
    status: str
    current_stage: str
    fraud_risk_level: Optional[str] = None
    assigned_adjuster_name: Optional[str] = None
    created_at: datetime


# ============================================================
# DOCUMENT SCHEMAS
# ============================================================

class DocumentUpload(BaseModel):
    """Schema for document upload metadata."""
    document_type: str
    file_name: str
    file_format: str
    file_size_bytes: int


class DocumentResponse(BaseModel):
    """Schema for document response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    claim_id: str
    document_type: str
    file_name: str
    file_format: str
    file_size_bytes: int
    file_path: str
    ocr_confidence: Optional[float] = None
    quality_score: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None


# ============================================================
# FRAUD DETECTION SCHEMAS
# ============================================================

class RedFlag(BaseModel):
    """Individual fraud red flag."""
    flag_id: str
    category: str
    description: str
    severity: str
    supporting_evidence: str


class FraudAnalysisResponse(BaseModel):
    """Schema for fraud analysis results."""
    fraud_analysis_id: str
    claim_id: str
    ml_scores: Dict[str, float]
    composite_fraud_score: int
    fraud_risk_level: str
    red_flags_detected: List[RedFlag]
    recommendation: str
    siu_referral_justification: Optional[str] = None
    analysis_timestamp: datetime


# ============================================================
# COVERAGE SCHEMAS
# ============================================================

class ExclusionReview(BaseModel):
    """Policy exclusion review."""
    exclusion_name: str
    policy_section: str
    page_number: str
    exact_language: str
    applies: bool
    analysis: str


class CoverageAnalysisResponse(BaseModel):
    """Schema for coverage analysis results."""
    coverage_analysis_id: str
    claim_id: str
    policy_number: str
    policy_form: str
    coverage_determination: str
    coverage_confidence: float
    covered_cause_of_loss: str
    applicable_limit: float
    applicable_deductible: float
    exclusions_reviewed: List[ExclusionReview]
    policy_citations: List[Dict[str, str]]
    requires_adjuster_decision: bool
    analysis_timestamp: datetime


# ============================================================
# PAYOUT SCHEMAS
# ============================================================

class DamageItem(BaseModel):
    """Individual damage item for payout calculation."""
    item: str
    rcn: float
    age_years: int
    depreciation_rate: float
    depreciation_amount: float
    acv: float


class SettlementWorksheet(BaseModel):
    """Settlement calculation worksheet."""
    total_rcn: float
    total_depreciation: float
    total_acv: float
    deductible: float
    prior_payments: float
    salvage_value: float
    net_settlement: float
    recoverable_depreciation_held: float
    total_loss_exposure: float


class PayoutAnalysisResponse(BaseModel):
    """Schema for payout analysis results."""
    payout_id: str
    claim_id: str
    loss_type: str
    valuation_basis: str
    damage_items: List[DamageItem]
    settlement_worksheet: SettlementWorksheet
    recommended_payment: float
    reserve_recommendation: float
    subrogation_potential: bool
    total_loss: bool
    payment_type: str
    analysis_timestamp: datetime


# ============================================================
# WEATHER VERIFICATION SCHEMAS
# ============================================================

class WeatherData(BaseModel):
    """Weather data from APIs."""
    sources_queried: List[str]
    temperature_f: Optional[float] = None
    wind_speed_mph: Optional[float] = None
    wind_gust_mph: Optional[float] = None
    precipitation_inches: Optional[float] = None
    hail_recorded: bool = False
    hail_size_inches: Optional[float] = None
    severe_weather_alert_active: bool = False
    alert_type: Optional[str] = None
    lightning_strikes_nearby: bool = False
    flood_advisory: bool = False
    data_confidence: str


class WeatherVerificationResponse(BaseModel):
    """Schema for weather verification results."""
    verification_id: str
    claim_id: str
    loss_location: str
    loss_date: datetime
    reported_cause: str
    weather_data: WeatherData
    verdict: str
    verdict_detail: str
    fraud_signal_to_fraud_agent: bool
    analysis_timestamp: datetime


# ============================================================
# AUDIT SCHEMAS
# ============================================================

class AuditLogEntry(BaseModel):
    """Individual audit log entry."""
    id: str
    claim_id: str
    action_type: str
    actor: str
    actor_type: str
    action_detail: str
    confidence_score: Optional[float] = None
    timestamp: datetime


class AuditReport(BaseModel):
    """Complete audit report for a claim."""
    audit_id: str
    claim_id: str
    regulatory_compliance: Dict[str, Any]
    bad_faith_risk_score: int
    bad_faith_risk_level: str
    file_completeness: Dict[str, Any]
    audit_trail: List[AuditLogEntry]
    overall_audit_status: str
    audit_timestamp: datetime


# ============================================================
# PIPELINE SCHEMAS
# ============================================================

class PipelineStatus(BaseModel):
    """Current pipeline status."""
    claim_id: str
    pipeline_type: str
    current_stage: str
    completed_agents: List[str]
    pending_agents: List[str]
    processing_start: datetime
    processing_time_seconds: Optional[int] = None
    status: str


class PipelineProgress(BaseModel):
    """Pipeline progress update."""
    claim_id: str
    stage: str
    status: str  # STARTED, COMPLETED, FAILED
    agent_name: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: datetime


# ============================================================
# API RESPONSE WRAPPERS
# ============================================================

class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel):
    """Paginated list response."""
    success: bool
    message: str
    data: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# HEALTH CHECK
# ============================================================

class HealthCheck(BaseModel):
    """Health check response."""
    status: str
    version: str
    database: str
    pinecone: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
