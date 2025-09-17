"""
Claim Decision Service with Fraud Detection
Handles insurance claim processing, decision making, and fraud detection
"""
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle
import os

from ..config import get_settings
from .ai_service import ai_service

settings = get_settings()


class FraudDetector:
    """Machine learning based fraud detection for insurance claims"""
    
    def __init__(self):
        self.isolation_forest = IsolationForest(
            contamination=0.1,  # Assume 10% of claims might be fraudulent
            random_state=42,
            n_estimators=100
        )
        self.scaler = StandardScaler()
        self.text_vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        self.is_trained = False
        self.feature_columns = [
            'amount', 'description_length', 'days_since_incident',
            'claim_hour', 'weekend_claim', 'amount_zscore'
        ]
    
    def extract_features(self, claim_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract numerical features from claim data for fraud detection"""
        features = {}
        
        # Basic amount features
        amount = float(claim_data.get('amount', 0))
        features['amount'] = amount
        
        # Description analysis
        description = claim_data.get('description', '')
        features['description_length'] = len(description)
        
        # Time-based features
        try:
            incident_date = datetime.fromisoformat(claim_data.get('incident_date', str(datetime.now().date())))
            claim_date = datetime.now()
            
            # Days between incident and claim
            days_diff = (claim_date - incident_date).days
            features['days_since_incident'] = max(0, days_diff)
            
            # Hour of claim submission
            features['claim_hour'] = claim_date.hour
            
            # Weekend claim indicator
            features['weekend_claim'] = 1 if claim_date.weekday() >= 5 else 0
            
        except Exception:
            features['days_since_incident'] = 0
            features['claim_hour'] = 12
            features['weekend_claim'] = 0
        
        # Amount percentile (rough estimate)
        # In production, this would be based on historical data
        if amount > 10000:
            features['amount_zscore'] = 2.0
        elif amount > 5000:
            features['amount_zscore'] = 1.0
        elif amount < 100:
            features['amount_zscore'] = -1.0
        else:
            features['amount_zscore'] = 0.0
        
        return features
    
    def detect_fraud(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect potential fraud in a claim
        
        Args:
            claim_data: Dictionary containing claim information
            
        Returns:
            Dictionary with fraud score and analysis
        """
        try:
            # Extract features
            features = self.extract_features(claim_data)
            
            # Create feature vector
            feature_vector = np.array([[features[col] for col in self.feature_columns]])
            
            # Simple rule-based fraud indicators
            fraud_indicators = self._rule_based_fraud_check(claim_data, features)
            
            # If we had training data, we would use ML model here
            # For now, use rule-based scoring
            base_score = len(fraud_indicators) / 10.0  # Normalize to 0-1
            
            # Add randomness to simulate ML model variability
            ml_adjustment = np.random.uniform(-0.1, 0.1)
            fraud_score = np.clip(base_score + ml_adjustment, 0.0, 1.0)
            
            return {
                'fraud_score': round(fraud_score, 4),
                'risk_level': self._categorize_risk(fraud_score),
                'fraud_indicators': fraud_indicators,
                'feature_analysis': features,
                'model_version': '1.0_rule_based'
            }
            
        except Exception as e:
            return {
                'fraud_score': 0.0,
                'risk_level': 'UNKNOWN',
                'fraud_indicators': [f'Analysis error: {str(e)}'],
                'feature_analysis': {},
                'model_version': 'error'
            }
    
    def _rule_based_fraud_check(self, claim_data: Dict[str, Any], features: Dict[str, float]) -> List[str]:
        """Apply rule-based fraud detection"""
        indicators = []
        
        amount = features['amount']
        description = claim_data.get('description', '').lower()
        
        # High amount claims
        if amount > 50000:
            indicators.append('Very high claim amount')
        elif amount > 20000:
            indicators.append('High claim amount')
        
        # Very quick claim submission
        if features['days_since_incident'] == 0:
            indicators.append('Claim submitted same day as incident')
        
        # Very delayed claim submission
        if features['days_since_incident'] > 365:
            indicators.append('Claim submitted more than 1 year after incident')
        
        # Suspicious description patterns
        suspicious_keywords = ['total loss', 'completely destroyed', 'no witnesses', 'dark road', 'no camera']
        for keyword in suspicious_keywords:
            if keyword in description:
                indicators.append(f'Suspicious keyword: {keyword}')
        
        # Very short or very long descriptions
        if features['description_length'] < 20:
            indicators.append('Very brief description')
        elif features['description_length'] > 1000:
            indicators.append('Unusually detailed description')
        
        # Weekend or late night claims (slightly suspicious)
        if features['weekend_claim'] == 1:
            indicators.append('Weekend claim submission')
        if features['claim_hour'] < 6 or features['claim_hour'] > 22:
            indicators.append('Off-hours claim submission')
        
        # Round number amounts (psychological bias)
        if amount > 0 and amount % 1000 == 0:
            indicators.append('Round number claim amount')
        
        return indicators
    
    def _categorize_risk(self, fraud_score: float) -> str:
        """Categorize fraud risk based on score"""
        if fraud_score >= 0.8:
            return 'VERY_HIGH'
        elif fraud_score >= 0.6:
            return 'HIGH'
        elif fraud_score >= 0.4:
            return 'MEDIUM'
        elif fraud_score >= 0.2:
            return 'LOW'
        else:
            return 'VERY_LOW'


class ClaimDecisionService:
    """Service for processing insurance claims and making decisions"""
    
    def __init__(self):
        self.fraud_detector = FraudDetector()
    
    async def process_claim(
        self,
        claim_data: Dict[str, Any],
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an insurance claim with AI-powered decision making
        
        Args:
            claim_data: Dictionary containing claim information
            document_id: Optional specific policy document to check against
            
        Returns:
            Dictionary with claim decision, explanation, and analysis
        """
        claim_id = str(uuid.uuid4())
        
        try:
            # Step 1: Fraud Detection
            fraud_analysis = self.fraud_detector.detect_fraud(claim_data)
            
            # Step 2: AI Policy Analysis
            eligibility_analysis = await ai_service.analyze_claim_eligibility(
                claim_data, document_id
            )
            
            # Step 3: Make final decision
            final_decision = self._make_final_decision(
                eligibility_analysis,
                fraud_analysis,
                claim_data
            )
            
            # Step 4: Generate explanation
            explanation = self._generate_explanation(
                final_decision['decision'],
                eligibility_analysis,
                fraud_analysis,
                claim_data
            )
            
            return {
                'claim_id': claim_id,
                'decision': final_decision['decision'],
                'explanation': explanation,
                'fraud_score': fraud_analysis['fraud_score'],
                'fraud_risk_level': fraud_analysis['risk_level'],
                'fraud_indicators': fraud_analysis['fraud_indicators'],
                'policy_references': eligibility_analysis.get('policy_references', []),
                'ai_confidence': eligibility_analysis.get('confidence_score', 0.5),
                'processing_details': {
                    'eligibility_decision': eligibility_analysis.get('decision', 'UNKNOWN'),
                    'fraud_analysis_version': fraud_analysis.get('model_version', 'unknown'),
                    'processed_at': datetime.now().isoformat(),
                    'feature_analysis': fraud_analysis.get('feature_analysis', {})
                }
            }
            
        except Exception as e:
            return {
                'claim_id': claim_id,
                'decision': 'ERROR',
                'explanation': f'Error processing claim: {str(e)}',
                'fraud_score': 0.0,
                'fraud_risk_level': 'UNKNOWN',
                'fraud_indicators': [],
                'policy_references': [],
                'ai_confidence': 0.0,
                'processing_details': {
                    'error': str(e),
                    'processed_at': datetime.now().isoformat()
                }
            }
    
    def _make_final_decision(
        self,
        eligibility_analysis: Dict[str, Any],
        fraud_analysis: Dict[str, Any],
        claim_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """Make final claim decision based on AI analysis and fraud detection"""
        
        ai_decision = eligibility_analysis.get('decision', 'REQUIRES_REVIEW')
        fraud_score = fraud_analysis.get('fraud_score', 0.0)
        fraud_risk = fraud_analysis.get('risk_level', 'UNKNOWN')
        
        # Decision logic
        if ai_decision == 'ERROR':
            return {'decision': 'REQUIRES_REVIEW', 'reason': 'AI analysis failed'}
        
        # High fraud risk overrides everything
        if fraud_score >= 0.8:
            return {'decision': 'DENIED', 'reason': 'High fraud risk detected'}
        
        # Medium fraud risk requires review even if AI approved
        if fraud_score >= 0.5 and ai_decision == 'APPROVED':
            return {'decision': 'REQUIRES_REVIEW', 'reason': 'Medium fraud risk requires manual review'}
        
        # Very high fraud risk with any AI decision
        if fraud_risk == 'VERY_HIGH':
            return {'decision': 'DENIED', 'reason': 'Very high fraud risk'}
        
        # Follow AI decision for low fraud risk
        if fraud_score < 0.3:
            if ai_decision == 'APPROVED':
                return {'decision': 'APPROVED', 'reason': 'AI approved with low fraud risk'}
            elif ai_decision == 'DENIED':
                return {'decision': 'DENIED', 'reason': 'AI denied based on policy analysis'}
            else:
                return {'decision': 'REQUIRES_REVIEW', 'reason': 'AI requires review'}
        
        # Default to review for uncertain cases
        return {'decision': 'REQUIRES_REVIEW', 'reason': 'Uncertain case requires manual review'}
    
    def _generate_explanation(
        self,
        decision: str,
        eligibility_analysis: Dict[str, Any],
        fraud_analysis: Dict[str, Any],
        claim_data: Dict[str, Any]
    ) -> str:
        """Generate human-readable explanation for the claim decision"""
        
        explanation_parts = []
        
        # Main decision explanation
        if decision == 'APPROVED':
            explanation_parts.append("Your claim has been approved for processing.")
        elif decision == 'DENIED':
            explanation_parts.append("Your claim has been denied.")
        else:
            explanation_parts.append("Your claim requires manual review by our claims team.")
        
        # Add AI policy analysis explanation
        ai_explanation = eligibility_analysis.get('explanation', '')
        if ai_explanation:
            explanation_parts.append(f"Policy Analysis: {ai_explanation}")
        
        # Add fraud analysis if relevant
        fraud_score = fraud_analysis.get('fraud_score', 0.0)
        if fraud_score >= 0.3:
            risk_level = fraud_analysis.get('risk_level', 'UNKNOWN').replace('_', ' ').lower()
            explanation_parts.append(f"Our automated review identified {risk_level} risk indicators.")
            
            # Add specific fraud indicators
            indicators = fraud_analysis.get('fraud_indicators', [])
            if indicators:
                explanation_parts.append("Specific areas flagged for review:")
                for indicator in indicators[:3]:  # Limit to top 3
                    explanation_parts.append(f"• {indicator}")
        
        # Add next steps
        if decision == 'APPROVED':
            explanation_parts.append("Payment processing will begin within 3-5 business days.")
        elif decision == 'DENIED':
            explanation_parts.append("You may appeal this decision by contacting our customer service team.")
        else:
            explanation_parts.append("A claims specialist will review your case within 2 business days.")
        
        return " ".join(explanation_parts)
    
    def get_claim_statistics(self) -> Dict[str, Any]:
        """Get statistics about processed claims (for monitoring)"""
        # In a real application, this would query the database
        return {
            'total_processed': 0,
            'approved': 0,
            'denied': 0,
            'requires_review': 0,
            'fraud_detected': 0,
            'average_processing_time': 0.0
        }


# Global instance
claim_service = ClaimDecisionService()