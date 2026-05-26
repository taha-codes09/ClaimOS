"""
Logging Configuration
=====================
Structured logging with Loguru and structlog for audit compliance.
"""
import sys
import logging
import structlog
from loguru import logger
from typing import Any, Dict
from datetime import datetime
import json

from .settings import settings


def setup_logging() -> None:
    """
    Configure application logging.
    - JSON format in production for log aggregation
    - Console format in development for readability
    """
    
    # Remove default handler
    logger.remove()
    
    # Add handler based on environment
    if settings.is_production:
        # JSON format for production
        logger.add(
            sys.stdout,
            format="{message}",
            level=settings.log_level,
            serialize=True  # JSON output
        )
        logger.add(
            "logs/app.log",
            rotation="100 MB",
            retention="30 days",
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name} | {function} | {message}"
        )
    else:
        # Colorized console format for development
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level=settings.log_level,
            colorize=True
        )
        logger.add(
            "logs/app.log",
            rotation="100 MB",
            retention="7 days",
            level=settings.log_level
        )
    
    # Configure structlog for structured logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.is_production else structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__):
    """
    Get a logger instance with the given name.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Processing claim", claim_id="CLM-001")
    """
    return logger.bind(module=name)


class AuditLogger:
    """
    Specialized logger for audit trail entries.
    Ensures all audit logs are immutable and properly formatted.
    """
    
    def __init__(self):
        self.logger = get_logger("audit")
    
    def log_action(
        self,
        claim_id: str,
        action_type: str,
        actor: str,
        actor_type: str,
        action_detail: str,
        data_sources: list = None,
        confidence: float = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Log an auditable action.
        Returns the audit entry for database storage.
        """
        timestamp = datetime.utcnow().isoformat()
        
        audit_entry = {
            "timestamp": timestamp,
            "claim_id": claim_id,
            "action_type": action_type,
            "actor": actor,
            "actor_type": actor_type,
            "action_detail": action_detail,
            "data_sources": data_sources or [],
            "confidence": confidence,
            **kwargs
        }
        
        # Log with full context
        self.logger.info(
            f"AUDIT: {action_type}",
            claim_id=claim_id,
            actor=actor,
            actor_type=actor_type,
            **audit_entry
        )
        
        return audit_entry
    
    def log_decision(
        self,
        claim_id: str,
        decision_type: str,
        actor: str,
        previous_value: Dict,
        new_value: Dict,
        rationale: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Log a decision made on a claim."""
        return self.log_action(
            claim_id=claim_id,
            action_type="DECISION",
            actor=actor,
            actor_type="AI_AGENT" if actor.endswith("Agent") else "HUMAN_ADJUSTER",
            action_detail=decision_type,
            previous_value=previous_value,
            new_value=new_value,
            decision_rationale=rationale,
            **kwargs
        )
    
    def log_error(
        self,
        claim_id: str,
        error_type: str,
        error_message: str,
        actor: str = "SYSTEM",
        **kwargs
    ) -> Dict[str, Any]:
        """Log an error for audit purposes."""
        return self.log_action(
            claim_id=claim_id,
            action_type="ERROR",
            actor=actor,
            actor_type="SYSTEM",
            action_detail=f"{error_type}: {error_message}",
            **kwargs
        )
    
    def log_communication(
        self,
        claim_id: str,
        communication_type: str,
        recipient: str,
        content: str,
        method: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Log a communication with claimant or third party."""
        return self.log_action(
            claim_id=claim_id,
            action_type="COMMUNICATION",
            actor="SYSTEM",
            actor_type="SYSTEM",
            action_detail=communication_type,
            recipient=recipient,
            content=content,
            method=method,
            **kwargs
        )


# Create audit logger instance
audit_logger = AuditLogger()


# ============================================================
# CLAIM PROCESSING LOGGING HELPERS
# ============================================================

def log_claim_event(event_type: str, claim_id: str, **kwargs):
    """Log a claim processing event."""
    logger = get_logger("claims")
    logger.info(f"CLAIM_EVENT: {event_type}", claim_id=claim_id, **kwargs)


def log_agent_execution(agent_name: str, claim_id: str, status: str, duration_ms: float, **kwargs):
    """Log agent execution metrics."""
    logger = get_logger("agents")
    logger.info(
        f"AGENT_EXECUTION: {agent_name}",
        agent_name=agent_name,
        claim_id=claim_id,
        status=status,
        duration_ms=duration_ms,
        **kwargs
    )


def log_fraud_detection(claim_id: str, fraud_score: int, risk_level: str, red_flags: list):
    """Log fraud detection results."""
    logger = get_logger("fraud")
    logger.warning(
        f"FRAUD_DETECTION: Score={fraud_score}, Level={risk_level}",
        claim_id=claim_id,
        fraud_score=fraud_score,
        risk_level=risk_level,
        red_flags_count=len(red_flags)
    )


def log_weather_verification(claim_id: str, verdict: str, data_confidence: str):
    """Log weather verification results."""
    logger = get_logger("weather")
    logger.info(
        f"WEATHER_VERIFICATION: {verdict}",
        claim_id=claim_id,
        verdict=verdict,
        data_confidence=data_confidence
    )


def log_pipeline_stage(claim_id: str, stage: str, status: str, **kwargs):
    """Log pipeline stage transition."""
    logger = get_logger("pipeline")
    logger.info(
        f"PIPELINE_STAGE: {stage} -> {status}",
        claim_id=claim_id,
        stage=stage,
        status=status,
        **kwargs
    )
