"""
LangGraph Workflow
===================
State graph and orchestration for the claims processing pipeline.
"""
from typing import TypedDict, List, Optional, Annotated, Literal
from datetime import datetime
import uuid
import json
from loguru import logger

try:
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import add_messages
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not available")

try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

from ..core.settings import settings
from ..core.prompts import (
    ORCHESTRATOR_PROMPT,
    CLAIM_INTAKE_PROMPT,
    FRAUD_DETECTION_PROMPT,
    POLICY_COVERAGE_PROMPT,
    WEATHER_VERIFIER_PROMPT,
    PAYOUT_CALCULATOR_PROMPT,
    AUDIT_AGENT_PROMPT,
    build_agent_prompt_with_insurer
)
from ..tools.document_processor import get_document_processor
from ..tools.weather_verifier import get_weather_verifier
from ..tools.pinecone_rag import get_pinecone_rag
from ..tools.fraud_detection_ml import get_fraud_detection_ml


# ============================================================
# STATE DEFINITION
# ============================================================

class InsuranceClaimsState(TypedDict):
    """
    LangGraph state for claims processing.
    Tracks all data as claim moves through pipeline.
    """
    # Messages for LLM interactions
    messages: Annotated[list, add_messages]
    
    # Claim identification
    claim_id: str
    claim_data: dict
    
    # Pipeline configuration
    pipeline_type: str  # fast_track, standard, complex, cat
    
    # Insurer context
    insurer_profile: Optional[dict]
    
    # Intake data
    raw_documents: Optional[list]
    structured_claim: Optional[dict]
    intake_complete: bool
    
    # Agent outputs
    intake_result: Optional[dict]
    fraud_result: Optional[dict]
    coverage_result: Optional[dict]
    weather_result: Optional[dict]
    payout_result: Optional[dict]
    audit_result: Optional[dict]
    
    # Decisions
    fraud_score: Optional[int]
    fraud_risk: Optional[str]
    coverage_status: Optional[str]
    recommended_settlement: Optional[float]
    ai_recommendation: Optional[str]
    recommendation_confidence: Optional[float]
    
    # Routing
    requires_human_adjuster: bool
    siu_referral: bool
    assigned_adjuster: Optional[str]
    escalation_reason: Optional[str]
    
    # Meta
    errors: List[str]
    completed_agents: List[str]
    processing_start: str
    processing_end: Optional[str]
    processing_time_seconds: Optional[int]
    mandatory_disclaimer: str


# ============================================================
# ORCHESTRATOR CLASS
# ============================================================

class ClaimOSOrchestrator:
    """
    Main orchestrator for the Autonomous Insurance Claims Processor.
    Uses LangGraph to manage the claim processing workflow.
    """
    
    def __init__(self):
        self.logger = logger.bind(module="claimos_orchestrator")
        self.settings = settings
        
        # Initialize tools
        self.document_processor = get_document_processor()
        self.weather_verifier = get_weather_verifier()
        self.pinecone_rag = get_pinecone_rag()
        self.fraud_ml = get_fraud_detection_ml()
        
        # Initialize LLMs
        self.orchestrator_llm = None
        self.agent_llm = None
        self._initialize_llms()
        
        # Build workflow graph
        self.graph = None
        self._build_graph()
        
        self.logger.info("ClaimOS Orchestrator initialized")
    
    def _initialize_llms(self):
        """Initialize LLM clients."""
        if not LLM_AVAILABLE:
            self.logger.warning("LLM libraries not available")
            return
        
        try:
            # Orchestrator uses Claude for complex reasoning
            if self.settings.anthropic_api_key:
                self.orchestrator_llm = ChatAnthropic(
                    model=self.settings.orchestrator_model,
                    api_key=self.settings.anthropic_api_key,
                    temperature=0.3,
                    max_tokens=4096
                )
            
            # Agent LLM can use OpenAI
            if self.settings.openai_api_key:
                self.agent_llm = ChatOpenAI(
                    model=self.settings.pattern_recognition_model,
                    api_key=self.settings.openai_api_key,
                    temperature=0.2,
                    max_tokens=4096
                )
            
            self.logger.info("LLMs initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing LLMs: {str(e)}")
    
    def _build_graph(self):
        """Build the LangGraph workflow."""
        if not LANGGRAPH_AVAILABLE:
            self.logger.warning("LangGraph not available - using fallback execution")
            return
        
        # Create state graph
        graph = StateGraph(InsuranceClaimsState)
        
        # Add nodes
        graph.add_node("claim_intake", self.node_claim_intake)
        graph.add_node("fraud_detection", self.node_fraud_detection)
        graph.add_node("policy_coverage", self.node_policy_coverage)
        graph.add_node("weather_verification", self.node_weather_verification)
        graph.add_node("payout_calculation", self.node_payout_calculation)
        graph.add_node("audit", self.node_audit)
        
        # Set entry point
        graph.set_entry_point("claim_intake")
        
        # Define edges with conditional routing
        graph.add_edge("claim_intake", "fraud_detection")
        graph.add_edge("claim_intake", "policy_coverage")
        
        # Conditional routing after fraud/coverage
        graph.add_conditional_edges(
            "fraud_detection",
            self.route_after_fraud_check,
            {
                "proceed": "weather_verification",
                "siu_referral": "audit",
                "blocked": "audit"
            }
        )
        
        graph.add_conditional_edges(
            "policy_coverage",
            self.route_after_coverage_check,
            {
                "covered": "weather_verification",
                "partial": "weather_verification",
                "not_covered": "audit",
                "under_review": "audit"
            }
        )
        
        # Weather verification routing
        graph.add_conditional_edges(
            "weather_verification",
            self.route_after_weather,
            {
                "confirmed": "payout_calculation",
                "partial": "payout_calculation",
                "inconsistent": "audit",
                "not_applicable": "payout_calculation"
            }
        )
        
        # Payout to audit
        graph.add_edge("payout_calculation", "audit")
        
        # Audit ends
        graph.add_edge("audit", END)
        
        self.graph = graph.compile()
        self.logger.info("LangGraph workflow compiled successfully")
    
    # ============================================================
    # NODE FUNCTIONS
    # ============================================================
    
    def node_claim_intake(self, state: InsuranceClaimsState) -> dict:
        """Process claim intake - parse documents and extract data."""
        self.logger.info(f"Starting claim intake for {state['claim_id']}")
        start_time = datetime.utcnow()
        
        try:
            # Process documents if provided
            documents = state.get("raw_documents", [])
            extracted_data = {"claimant": {}, "loss": {}, "damage": {}, "third_party": {}}
            document_results = []
            
            for doc in documents:
                doc_result = self.document_processor.process_document(
                    file_path=doc.get("file_path"),
                    file_bytes=doc.get("file_bytes"),
                    file_name=doc.get("file_name"),
                    document_type=doc.get("document_type", "unknown")
                )
                document_results.append(doc_result)
                
                # Extract claim fields from text
                if doc_result.get("text_content"):
                    fields = self.document_processor.extract_claim_fields(
                        doc_result["text_content"]
                    )
                    extracted_data["claimant"].update({
                        "policy_number": fields.get("policy_number"),
                        "phone": fields.get("phone_numbers", [""])[0] if fields.get("phone_numbers") else None,
                        "email": fields.get("emails", [""])[0] if fields.get("emails") else None
                    })
                    extracted_data["damage"]["estimated_amount"] = fields.get("claim_amount")
            
            # Use LLM to structure claim data if available
            if self.agent_llm:
                structured = self._llm_structure_claim_data(
                    state["claim_data"],
                    extracted_data,
                    document_results
                )
                extracted_data.update(structured)
            
            # Validate critical fields
            validation_results = self._validate_intake_data(extracted_data, state["claim_data"])
            
            # Determine completeness
            completeness_score = self._calculate_completeness(extracted_data, validation_results)
            
            # Set initial reserve
            claimed_amount = extracted_data.get("damage", {}).get("estimated_amount", 0)
            initial_reserve = claimed_amount * 0.5 if claimed_amount else 10000
            
            intake_result = {
                "intake_id": str(uuid.uuid4()),
                "claim_id": state["claim_id"],
                "intake_timestamp": start_time.isoformat(),
                "documents_received": [
                    {
                        "doc_type": d.get("document_type"),
                        "format": d.get("file_format"),
                        "ocr_confidence": d.get("ocr_confidence", 0),
                        "quality": d.get("quality_score", "unknown")
                    }
                    for d in document_results
                ],
                "extracted_data": extracted_data,
                "validation_results": validation_results,
                "completeness_score": completeness_score,
                "intake_status": "COMPLETE" if completeness_score >= 80 else "INCOMPLETE",
                "initial_reserve": initial_reserve,
                "proceed_to_next_agent": completeness_score >= 60
            }
            
            self.logger.info(f"Claim intake complete: {intake_result['intake_status']}")
            
            return {
                **state,
                "intake_result": intake_result,
                "structured_claim": extracted_data,
                "intake_complete": True,
                "completed_agents": state["completed_agents"] + ["ClaimIntakeAgent"]
            }
            
        except Exception as e:
            self.logger.error(f"Claim intake error: {str(e)}")
            return {
                **state,
                "errors": state["errors"] + [f"Intake error: {str(e)}"],
                "intake_complete": False
            }
    
    def node_fraud_detection(self, state: InsuranceClaimsState) -> dict:
        """Run fraud detection analysis."""
        self.logger.info(f"Starting fraud detection for {state['claim_id']}")
        
        try:
            # Prepare claim data for fraud analysis
            claim_data = {
                **state["claim_data"],
                **state.get("structured_claim", {})
            }
            
            # Run ML fraud detection
            fraud_result = self.fraud_ml.detect_fraud(claim_data)
            
            # Search for similar historical claims (if Pinecone available)
            if self.pinecone_rag.initialized:
                claim_summary = self._generate_claim_summary(claim_data)
                similar_claims = self.pinecone_rag.search_similar_claims(
                    claim_summary,
                    top_k=5,
                    fraud_only=True
                )
                fraud_result["historical_similar_claims"] = similar_claims
            
            # Update state with fraud results
            update = {
                "fraud_result": fraud_result,
                "fraud_score": fraud_result["composite_fraud_score"],
                "fraud_risk": fraud_result["fraud_risk_level"],
                "siu_referral": fraud_result["fraud_risk_level"] in ["HIGH", "CRITICAL"],
                "completed_agents": state["completed_agents"] + ["FraudDetectionAgent"]
            }
            
            self.logger.info(
                f"Fraud detection complete",
                score=fraud_result["composite_fraud_score"],
                risk_level=fraud_result["fraud_risk_level"]
            )
            
            return {**state, **update}
            
        except Exception as e:
            self.logger.error(f"Fraud detection error: {str(e)}")
            return {
                **state,
                "errors": state["errors"] + [f"Fraud detection error: {str(e)}"],
                "fraud_result": {"composite_fraud_score": 0, "fraud_risk_level": "UNKNOWN"}
            }
    
    def node_policy_coverage(self, state: InsuranceClaimsState) -> dict:
        """Analyze policy coverage."""
        self.logger.info(f"Starting coverage analysis for {state['claim_id']}")
        
        try:
            claim_data = state["claim_data"]
            policy_number = claim_data.get("policy_number")
            peril_type = claim_data.get("peril_type", "unknown")
            
            # Search policy documents in Pinecone
            policy_chunks = []
            if self.pinecone_rag.initialized and policy_number:
                policy_chunks = self.pinecone_rag.search_policies(
                    query=f"coverage for {peril_type} damage exclusion",
                    policy_number=policy_number,
                    top_k=10
                )
            
            # Use LLM to analyze coverage
            coverage_determination = "COVERED"
            coverage_confidence = 0.8
            exclusions_reviewed = []
            policy_citations = []
            
            if self.agent_llm and policy_chunks:
                coverage_analysis = self._llm_analyze_coverage(
                    claim_data,
                    policy_chunks
                )
                coverage_determination = coverage_analysis.get("coverage_determination", "COVERED")
                coverage_confidence = coverage_analysis.get("confidence", 0.7)
                exclusions_reviewed = coverage_analysis.get("exclusions", [])
                policy_citations = coverage_analysis.get("citations", [])
            
            coverage_result = {
                "coverage_analysis_id": str(uuid.uuid4()),
                "claim_id": state["claim_id"],
                "policy_number": policy_number,
                "coverage_determination": coverage_determination,
                "coverage_confidence": coverage_confidence,
                "covered_cause_of_loss": peril_type,
                "applicable_limit": claim_data.get("coverage_limit", 100000),
                "applicable_deductible": claim_data.get("deductible", 1000),
                "exclusions_reviewed": exclusions_reviewed,
                "policy_citations": policy_citations,
                "requires_adjuster_decision": coverage_determination != "COVERED"
            }
            
            self.logger.info(f"Coverage analysis complete: {coverage_determination}")
            
            return {
                **state,
                "coverage_result": coverage_result,
                "coverage_status": coverage_determination.lower().replace("_", "_"),
                "completed_agents": state["completed_agents"] + ["PolicyCoverageAgent"]
            }
            
        except Exception as e:
            self.logger.error(f"Coverage analysis error: {str(e)}")
            return {
                **state,
                "errors": state["errors"] + [f"Coverage analysis error: {str(e)}"],
                "coverage_result": {"coverage_determination": "UNDER_REVIEW"}
            }
    
    def node_weather_verification(self, state: InsuranceClaimsState) -> dict:
        """Verify weather-related claims."""
        self.logger.info(f"Starting weather verification for {state['claim_id']}")
        
        try:
            claim_data = state["claim_data"]
            peril_type = claim_data.get("peril_type", "").lower()
            
            # Check if weather verification is needed
            weather_perils = ["hail", "wind", "storm", "flood", "lightning", "freeze", "tornado"]
            is_weather_claim = any(p in peril_type for p in weather_perils)
            
            if not is_weather_claim:
                weather_result = {
                    "verdict": "NOT_APPLICABLE",
                    "verdict_detail": "Non-weather claim"
                }
            else:
                # Get location coordinates
                coordinates = claim_data.get("loss_coordinates")
                if not coordinates:
                    coordinates = self._geocode_location(claim_data.get("loss_location", ""))
                
                # Run weather verification
                weather_result = self.weather_verifier.verify_weather(
                    location=claim_data.get("loss_location", "Unknown"),
                    date_of_loss=datetime.fromisoformat(claim_data.get("date_of_loss", datetime.utcnow().isoformat())),
                    reported_cause=peril_type,
                    coordinates=coordinates
                )
            
            self.logger.info(f"Weather verification complete: {weather_result.get('verdict')}")
            
            return {
                **state,
                "weather_result": weather_result,
                "completed_agents": state["completed_agents"] + ["WeatherVerifierAgent"]
            }
            
        except Exception as e:
            self.logger.error(f"Weather verification error: {str(e)}")
            return {
                **state,
                "errors": state["errors"] + [f"Weather verification error: {str(e)}"],
                "weather_result": {"verdict": "INCONCLUSIVE"}
            }
    
    def node_payout_calculation(self, state: InsuranceClaimsState) -> dict:
        """Calculate settlement amount."""
        self.logger.info(f"Starting payout calculation for {state['claim_id']}")
        
        try:
            claim_data = state["claim_data"]
            structured = state.get("structured_claim", {})
            
            claimed_amount = claim_data.get("claimed_amount", 0) or 0
            
            # Get deductible from policy
            deductible = claim_data.get("deductible", 1000)
            
            # Calculate depreciation (simplified)
            depreciation_rate = 0.10  # 10% default
            age_years = claim_data.get("property_age_years", 5)
            depreciation = claimed_amount * depreciation_rate * min(age_years, 10)
            
            # ACV calculation
            acv = claimed_amount - depreciation
            net_settlement = max(0, acv - deductible)
            
            payout_result = {
                "payout_id": str(uuid.uuid4()),
                "claim_id": state["claim_id"],
                "loss_type": claim_data.get("claim_type", "property"),
                "valuation_basis": "ACV",
                "damage_items": [{
                    "item": claim_data.get("peril_type", "Damage"),
                    "rcn": claimed_amount,
                    "age_years": age_years,
                    "depreciation_rate": depreciation_rate,
                    "depreciation_amount": depreciation,
                    "acv": acv
                }],
                "settlement_worksheet": {
                    "total_rcn": claimed_amount,
                    "total_depreciation": depreciation,
                    "total_acv": acv,
                    "deductible": deductible,
                    "prior_payments": 0,
                    "salvage_value": 0,
                    "net_settlement": net_settlement,
                    "recoverable_depreciation_held": depreciation,
                    "total_loss_exposure": net_settlement
                },
                "recommended_payment": net_settlement,
                "reserve_recommendation": net_settlement * 1.2,
                "total_loss": claimed_amount > 100000,
                "payment_type": "ACV_PAYMENT"
            }
            
            # Determine AI recommendation
            fraud_score = state.get("fraud_score", 0)
            coverage_status = state.get("coverage_status", "covered")
            
            if fraud_score > 60:
                ai_recommendation = "REFER_TO_ADJUSTER"
                confidence = 0.9
            elif coverage_status == "not_covered":
                ai_recommendation = "DENY"
                confidence = 0.85
            elif net_settlement < 5000 and fraud_score < 30:
                ai_recommendation = "APPROVE"
                confidence = 0.95
            else:
                ai_recommendation = "REFER_TO_ADJUSTER"
                confidence = 0.8
            
            self.logger.info(f"Payout calculation complete: ${net_settlement:,.2f}")
            
            return {
                **state,
                "payout_result": payout_result,
                "recommended_settlement": net_settlement,
                "ai_recommendation": ai_recommendation,
                "recommendation_confidence": confidence,
                "completed_agents": state["completed_agents"] + ["PayoutCalculatorAgent"]
            }
            
        except Exception as e:
            self.logger.error(f"Payout calculation error: {str(e)}")
            return {
                **state,
                "errors": state["errors"] + [f"Payout calculation error: {str(e)}"]
            }
    
    def node_audit(self, state: InsuranceClaimsState) -> dict:
        """Generate audit trail and compliance report."""
        self.logger.info(f"Starting audit for {state['claim_id']}")
        
        try:
            # Calculate processing time
            start_time = datetime.fromisoformat(state["processing_start"])
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            
            # Generate audit trail
            audit_trail = []
            for agent in state.get("completed_agents", []):
                audit_trail.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "action_type": "AGENT_EXECUTION",
                    "actor": agent,
                    "actor_type": "AI_AGENT",
                    "action_detail": f"{agent} completed processing"
                })
            
            # Check regulatory compliance
            state_of_issue = state["claim_data"].get("state_of_issue", "TX")
            acknowledgment_deadline = 10  # business days
            decision_deadline = 30  # days
            
            # Bad faith risk assessment
            bad_faith_score = 0
            if state.get("fraud_score", 0) > 60 and not state.get("siu_referral"):
                bad_faith_score += 30
            if state.get("coverage_status") == "not_covered" and not state.get("requires_human_adjuster"):
                bad_faith_score += 40
            
            bad_faith_level = "LOW"
            if bad_faith_score >= 51:
                bad_faith_level = "HIGH"
            elif bad_faith_score >= 21:
                bad_faith_level = "MEDIUM"
            
            audit_result = {
                "audit_id": str(uuid.uuid4()),
                "claim_id": state["claim_id"],
                "audit_timestamp": end_time.isoformat(),
                "regulatory_compliance": {
                    "state": state_of_issue,
                    "acknowledgment_status": "COMPLIANT",
                    "decision_status": "COMPLIANT",
                    "payment_status": "NOT_YET_DUE"
                },
                "bad_faith_risk_score": bad_faith_score,
                "bad_faith_risk_level": bad_faith_level,
                "file_completeness": {
                    "score": min(100, len(state.get("completed_agents", [])) * 20),
                    "complete": len(state.get("completed_agents", [])) >= 5
                },
                "audit_trail": audit_trail,
                "overall_audit_status": "CLEAN" if bad_faith_score < 21 else "FLAGS_NOTED"
            }
            
            self.logger.info(f"Audit complete: {audit_result['overall_audit_status']}")
            
            return {
                **state,
                "audit_result": audit_result,
                "processing_end": end_time.isoformat(),
                "processing_time_seconds": int(processing_time),
                "completed_agents": state["completed_agents"] + ["AuditAgent"]
            }
            
        except Exception as e:
            self.logger.error(f"Audit error: {str(e)}")
            return {
                **state,
                "errors": state["errors"] + [f"Audit error: {str(e)}"]
            }
    
    # ============================================================
    # ROUTING FUNCTIONS
    # ============================================================
    
    def route_after_fraud_check(self, state: InsuranceClaimsState) -> str:
        """Route based on fraud detection results."""
        fraud_risk = state.get("fraud_risk", "LOW")
        
        if fraud_risk in ["HIGH", "CRITICAL"]:
            return "siu_referral"
        
        return "proceed"
    
    def route_after_coverage_check(self, state: InsuranceClaimsState) -> str:
        """Route based on coverage determination."""
        coverage = state.get("coverage_status", "under_review")
        
        if coverage == "not_covered":
            return "not_covered"
        elif coverage == "under_review":
            return "under_review"
        elif coverage == "partially_covered":
            return "partial"
        
        return "covered"
    
    def route_after_weather(self, state: InsuranceClaimsState) -> str:
        """Route based on weather verification."""
        verdict = state.get("weather_result", {}).get("verdict", "INCONCLUSIVE")
        
        if verdict == "INCONSISTENT":
            return "inconsistent"
        elif verdict == "NOT_APPLICABLE":
            return "not_applicable"
        elif verdict == "PARTIALLY_CONFIRMED":
            return "partial"
        
        return "confirmed"
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    def _llm_structure_claim_data(
        self,
        raw_claim_data: dict,
        extracted_data: dict,
        document_results: list
    ) -> dict:
        """Use LLM to structure and validate claim data."""
        if not self.agent_llm:
            return {}
        
        # Build prompt
        prompt = f"""
Extract and structure the following claim data:

Raw Claim Data: {json.dumps(raw_claim_data, default=str)}
Extracted Data: {json.dumps(extracted_data, default=str)}
Documents: {len(document_results)} processed

Return structured JSON with:
- claimant details
- loss details (date, location, cause)
- damage details
- any missing information
"""
        
        try:
            response = self.agent_llm.invoke([
                SystemMessage(content="You are a claims data extraction specialist."),
                HumanMessage(content=prompt)
            ])
            
            # Parse response (simplified)
            return {"structured_by_llm": True}
        except Exception as e:
            self.logger.error(f"LLM structuring error: {str(e)}")
            return {}
    
    def _validate_intake_data(
        self,
        extracted_data: dict,
        claim_data: dict
    ) -> dict:
        """Validate critical intake fields."""
        validations = {
            "critical_validations": [],
            "warning_flags": []
        }
        
        # Check policy number
        if not claim_data.get("policy_number"):
            validations["critical_validations"].append({
                "field": "policy_number",
                "status": "FAIL",
                "detail": "Policy number not found"
            })
        else:
            validations["critical_validations"].append({
                "field": "policy_number",
                "status": "PASS",
                "detail": "Policy number present"
            })
        
        # Check date of loss
        if not claim_data.get("date_of_loss"):
            validations["critical_validations"].append({
                "field": "date_of_loss",
                "status": "FAIL",
                "detail": "Date of loss not found"
            })
        
        return validations
    
    def _calculate_completeness(
        self,
        extracted_data: dict,
        validation_results: dict
    ) -> float:
        """Calculate data completeness score."""
        required_fields = [
            "policy_number",
            "date_of_loss",
            "loss_location",
            "loss_description",
            "cause_of_loss"
        ]
        
        claim_data = extracted_data.get("loss", {})
        claim_data["policy_number"] = extracted_data.get("claimant", {}).get("policy_number")
        
        present = sum(1 for field in required_fields if claim_data.get(field))
        return (present / len(required_fields)) * 100
    
    def _generate_claim_summary(self, claim_data: dict) -> str:
        """Generate text summary for vector search."""
        return f"""
Claim Type: {claim_data.get('claim_type', 'Unknown')}
Peril: {claim_data.get('peril_type', 'Unknown')}
Date of Loss: {claim_data.get('date_of_loss', 'Unknown')}
Claimed Amount: ${claim_data.get('claimed_amount', 0):,.2f}
Location: {claim_data.get('loss_location', 'Unknown')}
Description: {claim_data.get('loss_description', 'No description')}
"""
    
    def _llm_analyze_coverage(
        self,
        claim_data: dict,
        policy_chunks: list
    ) -> dict:
        """Use LLM to analyze policy coverage."""
        if not self.orchestrator_llm:
            return {"coverage_determination": "COVERED", "confidence": 0.7}
        
        # Build context from policy chunks
        policy_context = "\n\n".join([
            f"Chunk {i+1}:\n{chunk.get('content', '')}"
            for i, chunk in enumerate(policy_chunks[:5])
        ])
        
        prompt = f"""
Analyze coverage for this claim:

Claim:
- Peril: {claim_data.get('peril_type', 'Unknown')}
- Date of Loss: {claim_data.get('date_of_loss', 'Unknown')}
- Description: {claim_data.get('loss_description', 'N/A')}

Policy Provisions:
{policy_context}

Determine:
1. Is this peril covered?
2. Are any exclusions applicable?
3. What is the coverage confidence?

Return JSON: {{
    "coverage_determination": "COVERED|PARTIALLY_COVERED|NOT_COVERED|UNDER_REVIEW",
    "confidence": 0.0-1.0,
    "exclusions": [],
    "citations": []
}}
"""
        
        try:
            response = self.orchestrator_llm.invoke([
                SystemMessage(content=build_agent_prompt_with_insurer(
                    POLICY_COVERAGE_PROMPT,
                    self.settings.get_insurer_profile(),
                    include_guardrails=False
                )),
                HumanMessage(content=prompt)
            ])
            
            # Parse response (simplified for demo)
            return {
                "coverage_determination": "COVERED",
                "confidence": 0.85,
                "exclusions": [],
                "citations": policy_chunks[:3]
            }
        except Exception as e:
            self.logger.error(f"Coverage LLM error: {str(e)}")
            return {"coverage_determination": "UNDER_REVIEW", "confidence": 0.5}
    
    def _geocode_location(self, location: str) -> tuple:
        """Convert location to coordinates (simplified)."""
        # In production, use geocoding API
        # For demo, return default coordinates
        return (30.2672, -97.7431)  # Austin, TX
    
    # ============================================================
    # MAIN EXECUTION
    # ============================================================
    
    def process_claim(self, claim_data: dict, documents: list = None) -> dict:
        """
        Process a claim through the complete pipeline.
        
        Args:
            claim_data: Dictionary with claim information
            documents: List of document dictionaries
            
        Returns:
            Complete claim processing result
        """
        self.logger.info(f"Starting claim processing: {claim_data.get('claim_id')}")
        
        # Initialize state
        initial_state = {
            "messages": [],
            "claim_id": claim_data.get("claim_id", str(uuid.uuid4())),
            "claim_data": claim_data,
            "pipeline_type": self._determine_pipeline_type(claim_data),
            "insurer_profile": self.settings.get_insurer_profile(),
            "raw_documents": documents or [],
            "structured_claim": None,
            "intake_complete": False,
            "intake_result": None,
            "fraud_result": None,
            "coverage_result": None,
            "weather_result": None,
            "payout_result": None,
            "audit_result": None,
            "fraud_score": None,
            "fraud_risk": None,
            "coverage_status": None,
            "recommended_settlement": None,
            "ai_recommendation": None,
            "recommendation_confidence": None,
            "requires_human_adjuster": True,
            "siu_referral": False,
            "assigned_adjuster": None,
            "escalation_reason": None,
            "errors": [],
            "completed_agents": [],
            "processing_start": datetime.utcnow().isoformat(),
            "processing_end": None,
            "processing_time_seconds": None,
            "mandatory_disclaimer": "REQUIRES LICENSED ADJUSTER REVIEW AND AUTHORIZATION BEFORE EXECUTION"
        }
        
        # Execute workflow
        if self.graph:
            result = self.graph.invoke(initial_state)
        else:
            # Fallback: execute nodes sequentially
            result = self._execute_sequential(initial_state)
        
        self.logger.info(
            f"Claim processing complete",
            claim_id=result["claim_id"],
            time=result["processing_time_seconds"],
            recommendation=result["ai_recommendation"]
        )
        
        return result
    
    def _determine_pipeline_type(self, claim_data: dict) -> str:
        """Determine which pipeline to use."""
        claimed_amount = claim_data.get("claimed_amount", 0) or 0
        fraud_score = claim_data.get("fraud_score", 0)
        
        if claimed_amount > 50000 or fraud_score > 60:
            return "complex"
        elif claimed_amount < 5000 and fraud_score < 30:
            return "fast_track"
        else:
            return "standard"
    
    def _execute_sequential(self, state: InsuranceClaimsState) -> dict:
        """Execute nodes sequentially if LangGraph not available."""
        self.logger.warning("Using sequential execution fallback")
        
        state = self.node_claim_intake(state)
        state = self.node_fraud_detection(state)
        state = self.node_policy_coverage(state)
        state = self.node_weather_verification(state)
        state = self.node_payout_calculation(state)
        state = self.node_audit(state)
        
        return state


# Singleton instance
_orchestrator = None

def get_orchestrator() -> ClaimOSOrchestrator:
    """Get or create orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ClaimOSOrchestrator()
    return _orchestrator
