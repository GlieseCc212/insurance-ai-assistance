"""
AI Service for Query Understanding and Response Generation
Uses Google Generative AI for natural language processing and response generation
"""
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import json

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from ..config import get_settings
from .vector_store import rag_pipeline

settings = get_settings()


class AIService:
    """Service for AI-powered query understanding and response generation"""
    
    def __init__(self):
        # Configure Google Generative AI
        if settings.google_api_key:
            genai.configure(api_key=settings.google_api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None
            print("Warning: Google API key not configured. AI features will be limited.")
    
    async def answer_policy_question(
        self, 
        query: str, 
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Answer a question about an insurance policy using RAG
        
        Args:
            query: User's question about the policy
            document_id: Optional specific document to search
            
        Returns:
            Dictionary with answer, relevant clauses, and confidence scores
        """
        try:
            # Retrieve relevant context using RAG
            context, relevant_chunks = await rag_pipeline.retrieve_relevant_context(
                query=query,
                document_id=document_id,
                max_context_length=4000
            )
            
            if not context:
                return {
                    'answer': "I couldn't find relevant information in your policy documents to answer this question. Please make sure you've uploaded your policy documents first.",
                    'relevant_clauses': [],
                    'confidence_score': 0.0,
                    'source': 'no_context'
                }
            
            # Generate answer using AI model
            answer_data = await self._generate_answer_with_context(query, context)
            
            # Process relevant chunks for response
            processed_clauses = []
            for i, chunk in enumerate(relevant_chunks):
                clause_info = {
                    'text': chunk['content'][:500] + ('...' if len(chunk['content']) > 500 else ''),
                    'confidence': chunk['similarity_score'],
                    'section': f"Section {i + 1}",
                    'metadata': chunk.get('metadata', {})
                }
                processed_clauses.append(clause_info)
            
            return {
                'answer': answer_data['answer'],
                'relevant_clauses': processed_clauses,
                'confidence_score': answer_data.get('confidence_score', 0.8),
                'source': 'ai_generated',
                'context_used': len(context) > 0
            }
            
        except Exception as e:
            return {
                'answer': f"I encountered an error while processing your question: {str(e)}",
                'relevant_clauses': [],
                'confidence_score': 0.0,
                'source': 'error'
            }
    
    async def _generate_answer_with_context(self, query: str, context: str) -> Dict[str, Any]:
        """Generate answer using AI model with retrieved context"""
        
        if not self.model:
            return {
                'answer': "AI model not available. Please check your API configuration.",
                'confidence_score': 0.0
            }
        
        # Create a comprehensive prompt for insurance Q&A
        prompt = f"""You are an expert insurance policy analyst. Your job is to answer questions about insurance policies based on the provided policy text.

POLICY CONTEXT:
{context}

USER QUESTION: {query}

INSTRUCTIONS:
1. Provide a clear, accurate answer based ONLY on the information in the policy context above
2. If the policy doesn't contain enough information to answer the question, say so clearly
3. Reference specific clauses or sections when possible
4. Use plain language that a customer can understand
5. If there are conditions, exceptions, or limitations, mention them clearly
6. Be helpful but accurate - don't make assumptions beyond what's stated in the policy

ANSWER FORMAT:
- Start with a direct answer to the question
- Provide relevant details and conditions
- Mention any important limitations or exceptions
- If applicable, suggest contacting the insurance company for clarification

Answer:"""

        try:
            # Configure safety settings for insurance domain
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
            
            # Generate response
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt,
                    safety_settings=safety_settings,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.3,  # Lower temperature for more factual responses
                        top_p=0.8,
                        top_k=40,
                        max_output_tokens=1000,
                    )
                )
            )
            
            if response and response.text:
                return {
                    'answer': response.text.strip(),
                    'confidence_score': 0.85  # High confidence with context
                }
            else:
                return {
                    'answer': "I couldn't generate a response. Please try rephrasing your question.",
                    'confidence_score': 0.0
                }
                
        except Exception as e:
            return {
                'answer': f"Error generating AI response: {str(e)}",
                'confidence_score': 0.0
            }
    
    async def analyze_claim_eligibility(
        self,
        claim_data: Dict[str, Any],
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze claim eligibility based on policy documents
        
        Args:
            claim_data: Information about the claim
            document_id: Optional specific document to check against
            
        Returns:
            Dictionary with eligibility decision and explanation
        """
        try:
            # Create a query based on the claim
            eligibility_query = self._create_eligibility_query(claim_data)
            
            # Retrieve relevant policy sections
            context, relevant_chunks = await rag_pipeline.retrieve_relevant_context(
                query=eligibility_query,
                document_id=document_id,
                max_context_length=3000
            )
            
            if not context:
                return {
                    'decision': 'REQUIRES_REVIEW',
                    'explanation': 'Unable to find relevant policy information for this claim. Manual review required.',
                    'confidence_score': 0.0,
                    'policy_references': []
                }
            
            # Analyze eligibility using AI
            eligibility_result = await self._analyze_claim_with_ai(claim_data, context)
            
            # Process policy references
            policy_references = []
            for chunk in relevant_chunks[:3]:  # Top 3 most relevant
                policy_references.append({
                    'clause_text': chunk['content'][:300] + ('...' if len(chunk['content']) > 300 else ''),
                    'clause_number': f"Reference {len(policy_references) + 1}",
                    'relevance_score': chunk['similarity_score']
                })
            
            return {
                'decision': eligibility_result['decision'],
                'explanation': eligibility_result['explanation'],
                'confidence_score': eligibility_result.get('confidence_score', 0.7),
                'policy_references': policy_references,
                'reasoning_steps': eligibility_result.get('reasoning_steps', [])
            }
            
        except Exception as e:
            return {
                'decision': 'ERROR',
                'explanation': f'Error analyzing claim: {str(e)}',
                'confidence_score': 0.0,
                'policy_references': []
            }
    
    def _create_eligibility_query(self, claim_data: Dict[str, Any]) -> str:
        """Create a search query for claim eligibility check"""
        claim_type = claim_data.get('claim_type', 'general')
        amount = claim_data.get('amount', 0)
        description = claim_data.get('description', '')
        
        query_parts = [
            f"{claim_type} coverage",
            f"deductible",
            f"exclusions",
            f"limits"
        ]
        
        if description:
            # Extract key medical/service terms from description
            medical_terms = self._extract_medical_terms(description)
            query_parts.extend(medical_terms)
        
        return " ".join(query_parts)
    
    def _extract_medical_terms(self, description: str) -> List[str]:
        """Extract relevant medical/service terms from claim description"""
        # Simple keyword extraction - can be enhanced with NLP
        medical_keywords = [
            'surgery', 'emergency', 'hospital', 'doctor', 'treatment',
            'medication', 'therapy', 'diagnostic', 'procedure', 'consultation',
            'accident', 'injury', 'illness', 'condition', 'visit'
        ]
        
        description_lower = description.lower()
        found_terms = []
        
        for keyword in medical_keywords:
            if keyword in description_lower:
                found_terms.append(keyword)
        
        return found_terms[:5]  # Limit to avoid too long queries
    
    async def _analyze_claim_with_ai(self, claim_data: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Use AI to analyze claim eligibility against policy context"""
        
        if not self.model:
            return {
                'decision': 'REQUIRES_REVIEW',
                'explanation': 'AI analysis not available. Manual review required.',
                'confidence_score': 0.0
            }
        
        claim_info = f"""
Claim Type: {claim_data.get('claim_type', 'N/A')}
Amount: ${claim_data.get('amount', 0):,.2f}
Description: {claim_data.get('description', 'N/A')}
Date of Service: {claim_data.get('incident_date', 'N/A')}
"""
        
        prompt = f"""You are an insurance claims adjuster analyzing a claim for eligibility based on policy terms.

POLICY TERMS:
{context}

CLAIM INFORMATION:
{claim_info}

TASK: Determine if this claim is eligible for coverage based on the policy terms provided.

ANALYSIS REQUIREMENTS:
1. Check if the service/incident is covered under the policy
2. Verify if any exclusions apply
3. Consider deductibles and limits
4. Look for any waiting periods or pre-authorization requirements
5. Consider the claim amount against policy limits

RESPONSE FORMAT (JSON):
{{
    "decision": "APPROVED" | "DENIED" | "REQUIRES_REVIEW",
    "explanation": "Clear explanation in plain language referencing specific policy provisions",
    "confidence_score": 0.0-1.0,
    "reasoning_steps": ["step1", "step2", "step3"]
}}

Analyze the claim and provide your assessment:"""

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,  # Very low temperature for consistent decisions
                        top_p=0.9,
                        max_output_tokens=800,
                    )
                )
            )
            
            if response and response.text:
                # Try to parse JSON response
                try:
                    result = json.loads(response.text.strip())
                    return result
                except json.JSONDecodeError:
                    # If not valid JSON, parse manually
                    return self._parse_claim_analysis_text(response.text)
            else:
                return {
                    'decision': 'REQUIRES_REVIEW',
                    'explanation': 'Could not analyze claim. Manual review required.',
                    'confidence_score': 0.0
                }
                
        except Exception as e:
            return {
                'decision': 'ERROR',
                'explanation': f'Analysis error: {str(e)}',
                'confidence_score': 0.0
            }
    
    def _parse_claim_analysis_text(self, text: str) -> Dict[str, Any]:
        """Parse AI response text if JSON parsing fails"""
        # Simple text parsing as fallback
        text_lower = text.lower()
        
        if 'approved' in text_lower:
            decision = 'APPROVED'
        elif 'denied' in text_lower or 'reject' in text_lower:
            decision = 'DENIED'
        else:
            decision = 'REQUIRES_REVIEW'
        
        return {
            'decision': decision,
            'explanation': text.strip()[:500],
            'confidence_score': 0.6,
            'reasoning_steps': []
        }


# Global instance
ai_service = AIService()