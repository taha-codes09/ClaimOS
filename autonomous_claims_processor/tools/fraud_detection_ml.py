"""
Fraud Detection ML Tool
=======================
Machine learning models for fraud detection:
- Isolation Forest (anomaly detection)
- XGBoost (supervised classification)
- Graph analysis (fraud ring detection)
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
import hashlib
from pathlib import Path
from loguru import logger

try:
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    import xgboost as xgb
    import joblib
    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    logger.warning(f"ML libraries not fully available: {str(e)}")

from ..core.settings import settings


class FraudDetectionML:
    """
    Machine learning-based fraud detection.
    """
    
    def __init__(self, models_dir: str = None):
        self.logger = logger.bind(module="fraud_detection_ml")
        self.models_dir = models_dir or "models/fraud"
        
        self.isolation_forest = None
        self.xgboost_model = None
        self.scaler = None
        self.feature_columns = None
        
        self.initialized = False
        
        if ML_AVAILABLE:
            self._ensure_models_dir()
    
    def _ensure_models_dir(self):
        """Create models directory if not exists."""
        Path(self.models_dir).mkdir(parents=True, exist_ok=True)
    
    def initialize(self, train_if_needed: bool = True) -> bool:
        """
        Initialize ML models.
        Load from disk or train if not available.
        """
        if not ML_AVAILABLE:
            self.logger.warning("ML libraries not available - using rule-based fallback")
            return False
        
        try:
            # Try to load existing models
            if self._load_models():
                self.initialized = True
                self.logger.info("Fraud detection ML models loaded successfully")
                return True
            
            # Train new models if requested
            if train_if_needed:
                self.logger.info("Training new fraud detection models...")
                self._train_models()
                self.initialized = True
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error initializing fraud ML: {str(e)}")
            return False
    
    def _load_models(self) -> bool:
        """Load trained models from disk."""
        try:
            ift_path = Path(self.models_dir) / "isolation_forest.joblib"
            xgb_path = Path(self.models_dir) / "xgboost.joblib"
            scaler_path = Path(self.models_dir) / "scaler.joblib"
            features_path = Path(self.models_dir) / "feature_columns.json"
            
            if all(p.exists() for p in [ift_path, xgb_path, scaler_path, features_path]):
                self.isolation_forest = joblib.load(ift_path)
                self.xgboost_model = joblib.load(xgb_path)
                self.scaler = joblib.load(scaler_path)
                
                with open(features_path, 'r') as f:
                    self.feature_columns = json.load(f)
                
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"Error loading models: {str(e)}")
            return False
    
    def _save_models(self):
        """Save trained models to disk."""
        try:
            self._ensure_models_dir()
            
            joblib.dump(self.isolation_forest, Path(self.models_dir) / "isolation_forest.joblib")
            joblib.dump(self.xgboost_model, Path(self.models_dir) / "xgboost.joblib")
            joblib.dump(self.scaler, Path(self.models_dir) / "scaler.joblib")
            
            with open(Path(self.models_dir) / "feature_columns.json", 'w') as f:
                json.dump(self.feature_columns, f)
            
            self.logger.info("Fraud detection models saved")
        except Exception as e:
            self.logger.error(f"Error saving models: {str(e)}")
    
    def _train_models(self, training_data: pd.DataFrame = None):
        """
        Train fraud detection models.
        
        In production, you would load real historical claims data.
        For demo, we create synthetic training data.
        """
        if training_data is None:
            training_data = self._generate_synthetic_training_data()
        
        # Prepare features
        X = training_data[self.feature_columns]
        y = training_data['fraud_label']
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Isolation Forest (unsupervised anomaly detection)
        self.logger.info("Training Isolation Forest...")
        self.isolation_forest = IsolationForest(
            n_estimators=100,
            contamination=0.1,
            random_state=42,
            n_jobs=-1
        )
        self.isolation_forest.fit(X_scaled)
        
        # Train XGBoost (supervised)
        self.logger.info("Training XGBoost...")
        self.xgboost_model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='logloss',
            use_label_encoder=False
        )
        self.xgboost_model.fit(X_scaled, y)
        
        # Save models
        self._save_models()
    
    def _generate_synthetic_training_data(self, n_samples: int = 10000) -> pd.DataFrame:
        """Generate synthetic training data for demo purposes."""
        np.random.seed(42)
        
        data = {
            # Claim characteristics
            'claim_amount': np.random.exponential(10000, n_samples),
            'days_to_report': np.random.exponential(5, n_samples),
            'days_from_policy_start': np.random.exponential(200, n_samples),
            'prior_claims_count': np.random.poisson(1, n_samples),
            
            # Claimant characteristics  
            'claimant_age': np.random.normal(45, 15, n_samples),
            'policy_age_days': np.random.exponential(500, n_samples),
            
            # Claim type indicators
            'is_auto_claim': np.random.binomial(1, 0.4, n_samples),
            'is_property_claim': np.random.binomial(1, 0.35, n_samples),
            'is_health_claim': np.random.binomial(1, 0.15, n_samples),
            
            # Risk indicators
            'has_attorney': np.random.binomial(1, 0.1, n_samples),
            'is_weekend_loss': np.random.binomial(1, 0.28, n_samples),
            'has_witness': np.random.binomial(1, 0.3, n_samples),
            
            # Target
            'fraud_label': np.zeros(n_samples, dtype=int)
        }
        
        df = pd.DataFrame(data)
        
        # Create fraud patterns (10% fraud rate)
        n_fraud = int(n_samples * 0.1)
        fraud_indices = np.random.choice(n_samples, n_fraud, replace=False)
        
        # Fraud claims have distinct patterns
        df.loc[fraud_indices, 'claim_amount'] *= np.random.uniform(2, 5, n_fraud)
        df.loc[fraud_indices, 'days_to_report'] = np.random.exponential(2, n_fraud)
        df.loc[fraud_indices, 'days_from_policy_start'] = np.random.exponential(15, n_fraud)
        df.loc[fraud_indices, 'prior_claims_count'] = np.random.poisson(3, n_fraud)
        df.loc[fraud_indices, 'has_attorney'] = np.random.binomial(1, 0.4, n_fraud)
        
        df.loc[fraud_indices, 'fraud_label'] = 1
        
        self.feature_columns = list(df.columns)
        self.feature_columns.remove('fraud_label')
        
        return df
    
    def detect_fraud(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a claim for fraud indicators.
        
        Args:
            claim_data: Dictionary with claim features
            
        Returns:
            Fraud analysis results
        """
        result = {
            "fraud_analysis_id": f"FD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "ml_scores": {
                "isolation_forest_score": 0.0,
                "xgboost_fraud_probability": 0.0,
                "graph_network_score": 0.0
            },
            "composite_fraud_score": 0,
            "fraud_risk_level": "LOW",
            "red_flags_detected": [],
            "recommendation": "STANDARD_PROCESS"
        }
        
        if not self.initialized:
            self.logger.warning("ML not initialized - using rule-based detection")
            return self._rule_based_detection(claim_data)
        
        try:
            # Extract features
            features = self._extract_features(claim_data)
            X = np.array([[features.get(col, 0) for col in self.feature_columns]])
            X_scaled = self.scaler.transform(X)
            
            # Isolation Forest score
            if_scores = -self.isolation_forest.score_samples(X_scaled)[0]
            if_score_normalized = min(100, if_scores * 100)
            result["ml_scores"]["isolation_forest_score"] = round(if_score_normalized, 2)
            
            # XGBoost probability
            xgb_prob = self.xgboost_model.predict_proba(X_scaled)[0][1]
            xgb_score = xgb_prob * 100
            result["ml_scores"]["xgboost_fraud_probability"] = round(xgb_score, 2)
            
            # Graph analysis (simplified - would use network analysis in production)
            graph_score = self._analyze_network_patterns(claim_data)
            result["ml_scores"]["graph_network_score"] = round(graph_score, 2)
            
            # Ensemble score (weighted average)
            composite = (
                if_score_normalized * 0.30 +
                xgb_score * 0.50 +
                graph_score * 0.20
            )
            result["composite_fraud_score"] = round(composite)
            
            # Determine risk level
            if composite >= 81:
                result["fraud_risk_level"] = "CRITICAL"
                result["recommendation"] = "CLAIM_HOLD"
            elif composite >= 61:
                result["fraud_risk_level"] = "HIGH"
                result["recommendation"] = "SIU_REFERRAL"
            elif composite >= 31:
                result["fraud_risk_level"] = "MEDIUM"
                result["recommendation"] = "ENHANCED_REVIEW"
            else:
                result["fraud_risk_level"] = "LOW"
                result["recommendation"] = "STANDARD_PROCESS"
            
            # Detect specific red flags
            result["red_flags_detected"] = self._detect_red_flags(claim_data, result["ml_scores"])
            
            # SIU referral justification
            if result["recommendation"] == "SIU_REFERRAL":
                result["siu_referral_justification"] = self._generate_siu_justification(
                    claim_data, result["red_flags_detected"]
                )
            
            self.logger.info(
                f"Fraud analysis complete",
                score=result["composite_fraud_score"],
                risk_level=result["fraud_risk_level"]
            )
            
        except Exception as e:
            self.logger.error(f"Fraud detection error: {str(e)}")
            # Fallback to rule-based
            return self._rule_based_detection(claim_data)
        
        return result
    
    def _extract_features(self, claim_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract ML features from claim data."""
        features = {}
        
        # Claim amount (normalized)
        claimed_amount = claim_data.get("claimed_amount", 0) or 0
        features["claim_amount"] = claimed_amount / 10000  # Normalize
        
        # Days to report
        fnol = claim_data.get("fnol_received")
        loss_date = claim_data.get("date_of_loss")
        if fnol and loss_date:
            try:
                if isinstance(fnol, str):
                    fnol = datetime.fromisoformat(fnol.replace('Z', '+00:00'))
                if isinstance(loss_date, str):
                    loss_date = datetime.fromisoformat(loss_date.replace('Z', '+00:00'))
                features["days_to_report"] = (fnol - loss_date).days
            except:
                features["days_to_report"] = 0
        else:
            features["days_to_report"] = claim_data.get("days_to_report", 5)
        
        # Days from policy start (simplified)
        features["days_from_policy_start"] = claim_data.get("days_from_policy_start", 200)
        
        # Prior claims
        features["prior_claims_count"] = claim_data.get("prior_claims_count", 0)
        
        # Claimant age (if available)
        features["claimant_age"] = claim_data.get("claimant_age", 45)
        
        # Policy age
        features["policy_age_days"] = claim_data.get("policy_age_days", 500)
        
        # Claim type
        claim_type = claim_data.get("claim_type", "").lower()
        features["is_auto_claim"] = 1 if "auto" in claim_type else 0
        features["is_property_claim"] = 1 if "property" in claim_type else 0
        features["is_health_claim"] = 1 if "health" in claim_type else 0
        
        # Risk indicators
        features["has_attorney"] = 1 if claim_data.get("has_attorney", False) else 0
        features["is_weekend_loss"] = claim_data.get("is_weekend_loss", 0)
        features["has_witness"] = 1 if claim_data.get("has_witness", False) else 0
        
        return features
    
    def _analyze_network_patterns(self, claim_data: Dict[str, Any]) -> float:
        """
        Analyze network/fraud ring patterns.
        Simplified version - would use graph database in production.
        """
        score = 0.0
        
        # Check for suspicious patterns
        # In production, query PostgreSQL for:
        # - Same address, different claimants
        # - Same attorney + same provider combinations
        # - Clustering of claims by location/time
        
        # Simplified checks
        if claim_data.get("same_address_claims", 0) > 3:
            score += 30
        if claim_data.get("same_attorney_claims", 0) > 5:
            score += 25
        if claim_data.get("same_provider_claims", 0) > 10:
            score += 20
        
        return min(100, score)
    
    def _detect_red_flags(
        self,
        claim_data: Dict[str, Any],
        ml_scores: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Detect specific fraud red flags."""
        red_flags = []
        
        # Timing red flags
        days_from_policy_start = claim_data.get("days_from_policy_start", 365)
        if days_from_policy_start < 30:
            red_flags.append({
                "flag_id": "TIMING-001",
                "category": "timing",
                "description": "Policy purchased less than 30 days before loss",
                "severity": "HIGH",
                "supporting_evidence": f"Policy age: {days_from_policy_start} days"
            })
        
        days_to_report = claim_data.get("days_to_report", 5)
        if days_to_report > 30:
            red_flags.append({
                "flag_id": "TIMING-002",
                "category": "timing",
                "description": "Late notice of loss (>30 days)",
                "severity": "MEDIUM",
                "supporting_evidence": f"Days to report: {days_to_report}"
            })
        
        # Behavioral red flags
        if claim_data.get("has_attorney"):
            red_flags.append({
                "flag_id": "BEHAV-001",
                "category": "behavioral",
                "description": "Claimant represented by attorney immediately",
                "severity": "MEDIUM",
                "supporting_evidence": "Attorney involvement at first notice"
            })
        
        # Damage red flags
        claimed_amount = claim_data.get("claimed_amount", 0) or 0
        if claimed_amount > 50000:
            red_flags.append({
                "flag_id": "DAMAGE-001",
                "category": "damage",
                "description": "Unusually high claim amount",
                "severity": "MEDIUM",
                "supporting_evidence": f"Claimed amount: ${claimed_amount:,.2f}"
            })
        
        # ML-based flags
        if ml_scores.get("xgboost_fraud_probability", 0) > 70:
            red_flags.append({
                "flag_id": "ML-001",
                "category": "ml_anomaly",
                "description": "High fraud probability from ML model",
                "severity": "HIGH",
                "supporting_evidence": f"XGBoost probability: {ml_scores['xgboost_fraud_probability']:.1f}%"
            })
        
        if ml_scores.get("isolation_forest_score", 0) > 70:
            red_flags.append({
                "flag_id": "ML-002",
                "category": "ml_anomaly",
                "description": "Statistical anomaly detected",
                "severity": "MEDIUM",
                "supporting_evidence": f"Isolation Forest score: {ml_scores['isolation_forest_score']:.1f}"
            })
        
        return red_flags
    
    def _generate_siu_justification(
        self,
        claim_data: Dict[str, Any],
        red_flags: List[Dict[str, Any]]
    ) -> str:
        """Generate SIU referral justification."""
        high_severity = [f for f in red_flags if f.get("severity") == "HIGH"]
        
        justification_parts = [
            f"Fraud score: {claim_data.get('fraud_score', 'N/A')}",
            f"Red flags detected: {len(red_flags)}",
            f"High severity flags: {len(high_severity)}"
        ]
        
        for flag in high_severity[:3]:
            justification_parts.append(f"- {flag['description']}")
        
        return "\n".join(justification_parts)
    
    def _rule_based_detection(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback rule-based fraud detection when ML not available."""
        result = {
            "fraud_analysis_id": f"FD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "ml_scores": {
                "isolation_forest_score": 0.0,
                "xgboost_fraud_probability": 0.0,
                "graph_network_score": 0.0
            },
            "composite_fraud_score": 0,
            "fraud_risk_level": "LOW",
            "red_flags_detected": [],
            "recommendation": "STANDARD_PROCESS"
        }
        
        score = 0
        
        # Rule-based scoring
        if claim_data.get("days_from_policy_start", 365) < 30:
            score += 25
            result["red_flags_detected"].append({
                "flag_id": "RULE-001",
                "category": "timing",
                "description": "New policy claim (<30 days)",
                "severity": "MEDIUM"
            })
        
        if claim_data.get("claimed_amount", 0) > 50000:
            score += 15
        
        if claim_data.get("has_attorney"):
            score += 20
        
        if claim_data.get("prior_claims_count", 0) > 3:
            score += 20
        
        result["composite_fraud_score"] = min(100, score)
        
        if score >= 61:
            result["fraud_risk_level"] = "HIGH"
            result["recommendation"] = "SIU_REFERRAL"
        elif score >= 31:
            result["fraud_risk_level"] = "MEDIUM"
            result["recommendation"] = "ENHANCED_REVIEW"
        
        return result


# Singleton instance
_fraud_detection_ml = None

def get_fraud_detection_ml() -> FraudDetectionML:
    """Get or create fraud detection ML singleton."""
    global _fraud_detection_ml
    if _fraud_detection_ml is None:
        _fraud_detection_ml = FraudDetectionML()
    return _fraud_detection_ml
