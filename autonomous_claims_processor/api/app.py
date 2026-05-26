"""
FastAPI Application
===================
REST API for the Autonomous Insurance Claims Processor.
"""
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid
import json
from loguru import logger

from ..core.settings import settings
from ..core.logging_config import setup_logging, get_logger, audit_logger
from ..core.workflow import get_orchestrator
from ..database.connection import get_db, init_db, create_database
from ..database.repository import (
    ClaimRepository, PolicyRepository, ClaimDocumentRepository,
    AuditLogRepository, ReserveRepository
)
from ..models.schemas import (
    ClaimCreate, ClaimResponse, ClaimSummary,
    PolicyCreate, PolicyResponse,
    APIResponse, PaginatedResponse, HealthCheck,
    PipelineStatus, FraudRiskLevel, ClaimStatus
)


# ============================================================
# FASTAPI APP
# ============================================================

def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    # Setup logging
    setup_logging()
    log = get_logger(__name__)
    
    # Create app
    app = FastAPI(
        title="Autonomous Insurance Claims Processor",
        description="AI-powered claims processing system using LangGraph + CrewAI + Pinecone",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Startup event
    @app.on_event("startup")
    async def startup():
        log.info("Starting Autonomous Insurance Claims Processor...")
        
        # Initialize database
        try:
            create_database()
            init_db()
        except Exception as e:
            log.error(f"Database initialization error: {str(e)}")
        
        # Initialize orchestrator
        try:
            get_orchestrator()
            log.info("ClaimOS Orchestrator initialized")
        except Exception as e:
            log.error(f"Orchestrator initialization error: {str(e)}")
        
        log.info("Application startup complete")
    
    # Shutdown event
    @app.on_event("shutdown")
    async def shutdown():
        log.info("Application shutting down...")
    
    # Register routes
    register_routes(app)
    
    return app


# ============================================================
# ROUTES
# ============================================================

def register_routes(app: FastAPI):
    """Register all API routes."""
    
    # ---------------------------------------------------------
    # HEALTH CHECK
    # ---------------------------------------------------------
    @app.get("/health", response_model=HealthCheck, tags=["System"])
    async def health_check():
        """Health check endpoint."""
        return HealthCheck(
            status="healthy",
            version="1.0.0",
            database="connected",
            pinecone="configured" if settings.pinecone_api_key else "not_configured"
        )
    
    # ---------------------------------------------------------
    # POLICY MANAGEMENT
    # ---------------------------------------------------------
    @app.post("/policies", response_model=APIResponse, tags=["Policies"])
    async def create_policy(
        policy: PolicyCreate,
        db: Session = Depends(get_db)
    ):
        """Create a new insurance policy."""
        try:
            # Check for duplicate policy number
            existing = PolicyRepository.get_by_policy_number(db, policy.policy_number)
            if existing:
                raise HTTPException(status_code=400, detail="Policy number already exists")
            
            # Create policy
            policy_data = policy.model_dump()
            new_policy = PolicyRepository.create(db, policy_data)
            
            # Log audit
            audit_logger.log_action(
                claim_id="N/A",
                action_type="POLICY_CREATED",
                actor="API",
                actor_type="SYSTEM",
                action_detail=f"Policy {new_policy.policy_number} created"
            )
            
            return APIResponse(
                success=True,
                message=f"Policy {new_policy.policy_number} created successfully",
                data={"policy_id": str(new_policy.id), "policy_number": new_policy.policy_number}
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Create policy error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/policies/{policy_number}", response_model=PolicyResponse, tags=["Policies"])
    async def get_policy(
        policy_number: str,
        db: Session = Depends(get_db)
    ):
        """Get policy by policy number."""
        policy = PolicyRepository.get_by_policy_number(db, policy_number)
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        return policy
    
    # ---------------------------------------------------------
    # CLAIM SUBMISSION
    # ---------------------------------------------------------
    @app.post("/claims", response_model=APIResponse, tags=["Claims"])
    async def submit_claim(
        claim: ClaimCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
    ):
        """
        Submit a new insurance claim.
        Triggers the AI processing pipeline.
        """
        try:
            # Verify policy exists
            policy = PolicyRepository.get_by_policy_number(db, claim.policy_number)
            if not policy:
                raise HTTPException(status_code=400, detail="Policy not found")
            
            if policy.status != "ACTIVE":
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy is not active (status: {policy.status})"
                )
            
            # Generate claim ID
            claim_id = f"CLM-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            
            # Create claim record
            claim_data = {
                "claim_id": claim_id,
                "policy_id": policy.id,
                "claim_type": claim.claim_type.value,
                "peril_type": claim.peril_type,
                "date_of_loss": claim.loss.date_of_loss,
                "fnol_received": datetime.utcnow(),
                "claimant_name": claim.claimant.name,
                "claimant_phone": claim.claimant.phone,
                "claimant_email": claim.claimant.email,
                "claimant_address": claim.claimant.address,
                "loss_location": claim.loss.location,
                "loss_description": claim.loss.description,
                "loss_coordinates_lat": claim.loss.coordinates_lat,
                "loss_coordinates_lng": claim.loss.coordinates_lng,
                "claimed_amount": claim.claimed_amount or claim.damage.estimated_amount if claim.damage else None,
                "status": "OPEN",
                "current_stage": "INTAKE",
                "requires_human_adjuster": True,
                "mandatory_disclaimer": "REQUIRES LICENSED ADJUSTER REVIEW AND AUTHORIZATION BEFORE EXECUTION"
            }
            
            new_claim = ClaimRepository.create(db, claim_data)
            
            # Set initial reserve
            ReserveRepository.set_initial_reserve(
                db,
                new_claim.id,
                case_reserve=claim_data["claimed_amount"] or 10000,
                reason="Initial reserve on claim creation"
            )
            
            # Log audit
            audit_logger.log_action(
                claim_id=claim_id,
                action_type="CLAIM_SUBMITTED",
                actor=claim.claimant.name,
                actor_type="CLAIMANT",
                action_detail=f"New {claim.claim_type.value} claim submitted for peril: {claim.peril_type}"
            )
            
            # Start AI processing in background
            background_tasks.add_task(
                process_claim_async,
                claim_id=str(new_claim.id),
                claim_data=claim_data
            )
            
            return APIResponse(
                success=True,
                message=f"Claim {claim_id} submitted successfully. Processing started.",
                data={
                    "claim_id": claim_id,
                    "internal_id": str(new_claim.id),
                    "status": "PROCESSING"
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Submit claim error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/claims", response_model=PaginatedResponse, tags=["Claims"])
    async def list_claims(
        status: Optional[str] = None,
        fraud_risk: Optional[str] = None,
        assigned_adjuster: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = Depends(get_db)
    ):
        """List claims with optional filters."""
        try:
            claims = []
            
            if fraud_risk:
                claims = ClaimRepository.get_high_fraud_risk_claims(db, limit=page_size)
            elif assigned_adjuster:
                claims = ClaimRepository.get_claims_by_adjuster(db, assigned_adjuster, limit=page_size)
            elif status:
                claims = ClaimRepository.get_claims_by_status(db, status.upper(), limit=page_size)
            else:
                claims = ClaimRepository.get_claims_by_status(db, "OPEN", limit=page_size)
            
            return PaginatedResponse(
                success=True,
                message="Claims retrieved successfully",
                data=[
                    ClaimSummary(
                        claim_id=c.claim_id,
                        policy_number=c.policy.policy_number if c.policy else "N/A",
                        claimant_name=c.claimant_name,
                        claim_type=c.claim_type,
                        date_of_loss=c.date_of_loss,
                        claimed_amount=float(c.claimed_amount) if c.claimed_amount else None,
                        status=c.status,
                        current_stage=c.current_stage,
                        fraud_risk_level=c.fraud_risk_level,
                        assigned_adjuster_name=c.assigned_adjuster_name,
                        created_at=c.created_at
                    ).model_dump()
                    for c in claims
                ],
                total=len(claims),
                page=page,
                page_size=page_size,
                total_pages=(len(claims) + page_size - 1) // page_size
            )
        except Exception as e:
            logger.error(f"List claims error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/claims/{claim_id}", response_model=ClaimResponse, tags=["Claims"])
    async def get_claim(
        claim_id: str,
        db: Session = Depends(get_db)
    ):
        """Get claim by ID."""
        # Try by human-readable claim_id first
        claim = ClaimRepository.get_by_claim_id(db, claim_id)
        
        # Try by UUID if not found
        if not claim:
            try:
                claim = ClaimRepository.get_by_id(db, uuid.UUID(claim_id))
            except:
                pass
        
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        return claim
    
    @app.get("/claims/{claim_id}/status", response_model=PipelineStatus, tags=["Claims"])
    async def get_claim_status(
        claim_id: str,
        db: Session = Depends(get_db)
    ):
        """Get claim processing status."""
        claim = ClaimRepository.get_by_claim_id(db, claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        # Determine pending agents based on current stage
        all_agents = [
            "ClaimIntakeAgent",
            "FraudDetectionAgent",
            "PolicyCoverageAgent",
            "WeatherVerifierAgent",
            "PayoutCalculatorAgent",
            "AuditAgent"
        ]
        
        completed = claim.current_stage in ["COMPLETED", "AUDIT"]
        
        return PipelineStatus(
            claim_id=claim.claim_id,
            pipeline_type=claim.pipeline_type or "standard",
            current_stage=claim.current_stage,
            completed_agents=all_agents if completed else all_agents[:all_agents.index(claim.current_stage)] if claim.current_stage in all_agents else [],
            pending_agents=[] if completed else all_agents[all_agents.index(claim.current_stage):] if claim.current_stage in all_agents else all_agents,
            processing_start=claim.processing_start or claim.created_at,
            processing_time_seconds=claim.processing_time_seconds,
            status=claim.status
        )
    
    @app.get("/claims/{claim_id}/audit", response_model=APIResponse, tags=["Claims"])
    async def get_claim_audit(
        claim_id: str,
        db: Session = Depends(get_db)
    ):
        """Get audit trail for a claim."""
        claim = ClaimRepository.get_by_claim_id(db, claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        audit_logs = AuditLogRepository.get_by_claim(db, claim.id)
        
        return APIResponse(
            success=True,
            message="Audit trail retrieved",
            data={
                "claim_id": claim.claim_id,
                "audit_entries": [
                    {
                        "timestamp": log.timestamp.isoformat(),
                        "action_type": log.action_type,
                        "actor": log.actor,
                        "action_detail": log.action_detail,
                        "confidence_score": log.confidence_score
                    }
                    for log in audit_logs
                ],
                "total_entries": len(audit_logs)
            }
        )
    
    # ---------------------------------------------------------
    # CLAIM PROCESSING (Manual trigger)
    # ---------------------------------------------------------
    @app.post("/claims/{claim_id}/process", response_model=APIResponse, tags=["Claims"])
    async def process_claim_manual(
        claim_id: str,
        db: Session = Depends(get_db)
    ):
        """Manually trigger claim processing."""
        claim = ClaimRepository.get_by_claim_id(db, claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        if claim.status == "CLOSED":
            raise HTTPException(status_code=400, detail="Cannot process closed claim")
        
        # Build claim data for processing
        claim_data = {
            "claim_id": claim.claim_id,
            "policy_number": claim.policy.policy_number if claim.policy else None,
            "claim_type": claim.claim_type,
            "peril_type": claim.peril_type,
            "date_of_loss": claim.date_of_loss.isoformat() if claim.date_of_loss else None,
            "fnol_received": claim.fnol_received.isoformat() if claim.fnol_received else None,
            "claimed_amount": float(claim.claimed_amount) if claim.claimed_amount else None,
            "loss_location": claim.loss_location,
            "loss_description": claim.loss_description,
            "loss_coordinates": (claim.loss_coordinates_lat, claim.loss_coordinates_lng) if claim.loss_coordinates_lat else None,
            "deductible": float(claim.policy.all_peril_deductible) if claim.policy and claim.policy.all_peril_deductible else 1000,
            "coverage_limit": float(claim.policy.coverage_a_limit) if claim.policy and claim.policy.coverage_a_limit else 100000,
            "state_of_issue": claim.policy.state_of_issue if claim.policy else "TX"
        }
        
        # Process claim
        orchestrator = get_orchestrator()
        result = orchestrator.process_claim(claim_data)
        
        # Update claim in database
        ClaimRepository.update(db, claim.id, {
            "current_stage": "COMPLETED",
            "fraud_score": result.get("fraud_score", 0),
            "fraud_risk_level": result.get("fraud_risk", "LOW"),
            "coverage_status": result.get("coverage_status", "under_review"),
            "recommended_settlement": result.get("recommended_settlement"),
            "ai_recommendation": result.get("ai_recommendation"),
            "recommendation_confidence": result.get("recommendation_confidence"),
            "siu_referral": result.get("siu_referral", False),
            "requires_human_adjuster": result.get("requires_human_adjuster", True),
            "processing_end": datetime.utcnow(),
            "processing_time_seconds": result.get("processing_time_seconds")
        })
        
        # Log audit
        audit_logger.log_action(
            claim_id=claim.claim_id,
            action_type="CLAIM_PROCESSED",
            actor="ClaimOS",
            actor_type="AI_AGENT",
            action_detail=f"Claim processed. Recommendation: {result.get('ai_recommendation')}",
            confidence=result.get("recommendation_confidence")
        )
        
        return APIResponse(
            success=True,
            message="Claim processed successfully",
            data={
                "claim_id": claim.claim_id,
                "ai_recommendation": result.get("ai_recommendation"),
                "recommended_settlement": result.get("recommended_settlement"),
                "fraud_score": result.get("fraud_score"),
                "coverage_status": result.get("coverage_status"),
                "requires_human_review": result.get("requires_human_adjuster", True),
                "processing_time_seconds": result.get("processing_time_seconds"),
                "mandatory_disclaimer": result.get("mandatory_disclaimer")
            }
        )
    
    # ---------------------------------------------------------
    # DOCUMENT UPLOAD
    # ---------------------------------------------------------
    @app.post("/claims/{claim_id}/documents", response_model=APIResponse, tags=["Documents"])
    async def upload_document(
        claim_id: str,
        document_type: str,
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
    ):
        """Upload a document for a claim."""
        claim = ClaimRepository.get_by_claim_id(db, claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        try:
            # Read file content
            file_content = await file.read()
            
            # Save document (in production, upload to S3)
            file_path = f"documents/{claim_id}/{file.filename}"
            
            # Create document record
            doc_data = {
                "claim_id": claim.id,
                "document_type": document_type,
                "file_name": file.filename,
                "file_format": file.content_type.split("/")[-1].upper() if file.content_type else "UNKNOWN",
                "file_size_bytes": len(file_content),
                "file_path": file_path,
                "quality_score": "pending"
            }
            
            new_doc = ClaimDocumentRepository.create(db, doc_data)
            
            # Process document (OCR, extraction)
            # In production, this would be async
            from ..tools.document_processor import get_document_processor
            processor = get_document_processor()
            
            # Save temp file for processing
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}") as f:
                f.write(file_content)
                temp_path = f.name
            
            doc_result = processor.process_document(
                file_path=temp_path,
                file_name=file.filename,
                document_type=document_type
            )
            
            # Update document with OCR results
            ClaimDocumentRepository.update_ocr_data(
                db,
                new_doc.id,
                ocr_text=doc_result.get("text_content", ""),
                ocr_confidence=doc_result.get("ocr_confidence", 0)
            )
            
            return APIResponse(
                success=True,
                message="Document uploaded and processed",
                data={
                    "document_id": str(new_doc.id),
                    "ocr_confidence": doc_result.get("ocr_confidence"),
                    "quality_score": doc_result.get("quality_score")
                }
            )
            
        except Exception as e:
            logger.error(f"Document upload error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# BACKGROUND TASKS
# ============================================================

def process_claim_async(claim_id: str, claim_data: dict):
    """Process claim asynchronously in background."""
    try:
        logger = get_logger("background")
        logger.info(f"Background processing started for claim {claim_id}")
        
        orchestrator = get_orchestrator()
        result = orchestrator.process_claim(claim_data)
        
        logger.info(
            f"Background processing complete",
            claim_id=claim_id,
            recommendation=result.get("ai_recommendation")
        )
        
    except Exception as e:
        logger.error(f"Background processing error: {str(e)}")


# ============================================================
# EXCEPTION HANDLERS
# ============================================================

def create_app_with_exception_handlers() -> FastAPI:
    """Create app with custom exception handlers."""
    app = create_app()
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error",
                "detail": str(exc) if settings.app_debug else "An error occurred"
            }
        )
    
    return app


# Create app instance
app = create_app_with_exception_handlers()


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "autonomous_claims_processor.api.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug
    )
