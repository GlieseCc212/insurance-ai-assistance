"""
Pydantic Models for API Request/Response Schemas
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class DocumentResponse(BaseModel):
    """Response model for document upload"""
    success: bool
    document_id: str
    filename: str
    pages_processed: int
    chunks_created: int
    processing_time: float
    vector_storage: Dict[str, Any]
    database_record_id: Optional[str] = None


class DocumentInfo(BaseModel):
    """Document information model"""
    document_id: str
    filename: str
    file_type: str
    policy_type: Optional[str] = None
    text_length: int
    pages_processed: int
    chunks_created: int
    processing_time: float
    upload_timestamp: datetime
    status: str


class DocumentListResponse(BaseModel):
    """Response model for document listing"""
    documents: List[DocumentInfo]
    total: int
    limit: int
    offset: int


class QueryRequest(BaseModel):
    """Request model for policy questions"""
    query: str = Field(..., description="User's question about the policy")
    document_id: Optional[str] = Field(None, description="Optional specific document to search")


class ClauseInfo(BaseModel):
    """Information about a relevant policy clause"""
    text: str
    confidence: float
    section: str
    metadata: Dict[str, Any] = {}


class QueryResponse(BaseModel):
    """Response model for policy questions"""
    answer: str
    relevant_clauses: List[ClauseInfo]
    confidence_score: float
    source: str
    context_used: bool


class ClaimRequest(BaseModel):
    """Request model for insurance claims"""
    claim_type: str = Field(..., description="Type of claim (medical, dental, vision, accident, property, other)")
    amount: float = Field(..., description="Claim amount in dollars")
    description: str = Field(..., description="Description of the incident or service")
    incident_date: str = Field(..., description="Date of incident or service (YYYY-MM-DD)")
    document_id: Optional[str] = Field(None, description="Related policy document ID")


class PolicyReference(BaseModel):
    """Reference to a policy clause"""
    clause_text: str
    clause_number: str
    relevance_score: Optional[float] = None


class ClaimResponse(BaseModel):
    """Response model for claim processing"""
    claim_id: str
    decision: str
    explanation: str
    fraud_score: float
    fraud_risk_level: str
    fraud_indicators: List[str]
    policy_references: List[PolicyReference]
    ai_confidence: float
    processing_details: Dict[str, Any]


class ClaimInfo(BaseModel):
    """Claim information model"""
    claim_id: str
    document_id: Optional[str]
    claim_type: str
    amount: float
    description: str
    incident_date: str
    decision: str
    explanation: str
    fraud_score: float
    fraud_risk_level: str
    ai_confidence: float
    created_at: datetime
    status: str


class ClaimListResponse(BaseModel):
    """Response model for claim listing"""
    claims: List[ClaimInfo]
    total: int
    limit: int
    offset: int


class SystemStats(BaseModel):
    """System statistics model"""
    timestamp: datetime
    statistics: Dict[str, Any]


class HealthStatus(BaseModel):
    """Health check response model"""
    status: str
    timestamp: str
    version: str
    service: str


class DetailedHealthStatus(BaseModel):
    """Detailed health check response model"""
    status: str
    timestamp: str
    version: str
    services: Dict[str, Any]


class NotificationRequest(BaseModel):
    """Request model for notifications"""
    message: str
    alert_type: str = "info"
    email: Optional[str] = None
    phone: Optional[str] = None


class NotificationResponse(BaseModel):
    """Response model for notifications"""
    email: Optional[Dict[str, Any]] = None
    sms: Optional[Dict[str, Any]] = None
    success: bool