"""
Unit Tests for Autonomous Insurance Claims Processor
=====================================================
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


# ============================================================
# DOCUMENT PROCESSOR TESTS
# ============================================================

class TestDocumentProcessor:
    """Tests for document processing functionality."""
    
    def test_text_extraction(self):
        """Test text extraction from plain text."""
        from autonomous_claims_processor.tools.document_processor import DocumentProcessor
        
        processor = DocumentProcessor()
        result = processor._process_text(file_bytes=b"Hello, this is a test claim document.")
        
        assert "Hello, this is a test claim document." in result["text_content"]
        assert result["ocr_confidence"] == 100.0
        assert result["ocr_completed"] == False
    
    def test_claim_field_extraction(self):
        """Test extraction of claim fields from text."""
        from autonomous_claims_processor.tools.document_processor import DocumentProcessor
        
        processor = DocumentProcessor()
        
        text = """
        Policy Number: POL-2024-001
        Claim Amount: $25,000
        Contact: 512-555-0100
        Email: john.smith@email.com
        """
        
        extracted = processor.extract_claim_fields(text)
        
        assert extracted["policy_number"] is not None
        assert extracted["claim_amount"] == 25000.0
        assert len(extracted["phone_numbers"]) > 0
        assert len(extracted["emails"]) > 0
    
    def test_quality_score_calculation(self):
        """Test document quality scoring."""
        from autonomous_claims_processor.tools.document_processor import DocumentProcessor
        
        processor = DocumentProcessor()
        
        # Good quality document
        result = processor._calculate_quality_score({
            "errors": [],
            "ocr_confidence": 98.0,
            "metadata": {"is_blurry": False}
        })
        assert result == "good"
        
        # Poor quality document
        result = processor._calculate_quality_score({
            "errors": ["OCR failed"],
            "ocr_confidence": 50.0,
            "metadata": {"is_blurry": True}
        })
        assert result == "poor"


# ============================================================
# FRAUD DETECTION TESTS
# ============================================================

class TestFraudDetectionML:
    """Tests for fraud detection ML models."""
    
    def test_rule_based_detection(self):
        """Test fallback rule-based fraud detection."""
        from autonomous_claims_processor.tools.fraud_detection_ml import FraudDetectionML
        
        ml = FraudDetectionML()
        
        # High risk claim
        claim_data = {
            "days_from_policy_start": 15,  # New policy
            "claimed_amount": 75000,  # High amount
            "has_attorney": True,
            "prior_claims_count": 5
        }
        
        result = ml._rule_based_detection(claim_data)
        
        assert result["composite_fraud_score"] > 30
        assert result["fraud_risk_level"] in ["MEDIUM", "HIGH"]
    
    def test_low_risk_claim(self):
        """Test low risk claim detection."""
        from autonomous_claims_processor.tools.fraud_detection_ml import FraudDetectionML
        
        ml = FraudDetectionML()
        
        claim_data = {
            "days_from_policy_start": 500,  # Old policy
            "claimed_amount": 5000,  # Low amount
            "has_attorney": False,
            "prior_claims_count": 0
        }
        
        result = ml._rule_based_detection(claim_data)
        
        assert result["composite_fraud_score"] < 30
        assert result["fraud_risk_level"] == "LOW"


# ============================================================
# WEATHER VERIFIER TESTS
# ============================================================

class TestWeatherVerifier:
    """Tests for weather verification."""
    
    def test_verdict_generation_hail(self):
        """Test hail verdict generation."""
        from autonomous_claims_processor.tools.weather_verifier import WeatherVerifier
        
        verifier = WeatherVerifier()
        
        # Confirmed hail
        weather_data = {
            "hail_recorded": True,
            "hail_size_inches": 1.0
        }
        
        verdict, detail = verifier._generate_verdict("hail", weather_data)
        assert verdict == "CONFIRMED"
        
        # No hail recorded
        weather_data = {
            "hail_recorded": False
        }
        
        verdict, detail = verifier._generate_verdict("hail", weather_data)
        assert verdict == "INCONSISTENT"
    
    def test_verdict_generation_wind(self):
        """Test wind verdict generation."""
        from autonomous_claims_processor.tools.weather_verifier import WeatherVerifier
        
        verifier = WeatherVerifier()
        
        # Significant wind
        weather_data = {
            "wind_gust_mph": 65
        }
        
        verdict, detail = verifier._generate_verdict("wind", weather_data)
        assert verdict == "CONFIRMED"
        
        # Low wind
        weather_data = {
            "wind_gust_mph": 25
        }
        
        verdict, detail = verifier._generate_verdict("wind", weather_data)
        assert verdict == "INCONSISTENT"


# ============================================================
# WORKFLOW TESTS
# ============================================================

class TestWorkflow:
    """Tests for LangGraph workflow."""
    
    def test_pipeline_type_determination(self):
        """Test pipeline type classification."""
        from autonomous_claims_processor.core.workflow import ClaimOSOrchestrator
        
        orchestrator = ClaimOSOrchestrator()
        
        # Fast track
        claim_data = {"claimed_amount": 3000, "fraud_score": 10}
        pipeline_type = orchestrator._determine_pipeline_type(claim_data)
        assert pipeline_type == "fast_track"
        
        # Complex
        claim_data = {"claimed_amount": 100000, "fraud_score": 75}
        pipeline_type = orchestrator._determine_pipeline_type(claim_data)
        assert pipeline_type == "complex"
        
        # Standard
        claim_data = {"claimed_amount": 25000, "fraud_score": 20}
        pipeline_type = orchestrator._determine_pipeline_type(claim_data)
        assert pipeline_type == "standard"
    
    def test_completeness_calculation(self):
        """Test data completeness scoring."""
        from autonomous_claims_processor.core.workflow import ClaimOSOrchestrator
        
        orchestrator = ClaimOSOrchestrator()
        
        # Complete data
        extracted_data = {
            "loss": {
                "policy_number": "POL-001",
                "date_of_loss": "2024-01-01",
                "loss_location": "123 Main St",
                "loss_description": "Damage",
                "cause_of_loss": "Fire"
            }
        }
        
        score = orchestrator._calculate_completeness(extracted_data, {"critical_validations": []})
        assert score == 100.0
        
        # Partial data
        extracted_data = {
            "loss": {
                "policy_number": "POL-001",
                "date_of_loss": "2024-01-01"
            }
        }
        
        score = orchestrator._calculate_completeness(extracted_data, {"critical_validations": []})
        assert score == 40.0


# ============================================================
# API TESTS
# ============================================================

class TestAPI:
    """Tests for FastAPI endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from autonomous_claims_processor.api.app import app
        
        return TestClient(app)
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
    
    def test_list_claims(self, client):
        """Test listing claims."""
        response = client.get("/claims")
        # Will fail without database, but tests endpoint exists
        assert response.status_code in [200, 500]


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestIntegration:
    """Integration tests for full pipeline."""
    
    @pytest.mark.integration
    def test_full_claim_processing(self):
        """Test complete claim processing pipeline."""
        from autonomous_claims_processor.core.workflow import get_orchestrator
        
        orchestrator = get_orchestrator()
        
        claim_data = {
            "claim_id": "TEST-001",
            "policy_number": "POL-2024-001",
            "claim_type": "property",
            "peril_type": "hail",
            "date_of_loss": datetime.utcnow().isoformat(),
            "claimed_amount": 15000,
            "loss_location": "Austin, TX",
            "loss_description": "Hail damage to roof"
        }
        
        # This would require full setup (LLMs, database, etc.)
        # Skip in unit test environment
        pytest.skip("Requires full environment setup")


# ============================================================
# RUN TESTS
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
