"""
Claims Router
Handles insurance claim processing with AI-powered decision making
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from datetime import datetime

from ..services.claim_service import claim_service
from ..services.notification_service import notification_service
from ..database import get_claim_repo
from ..models.schemas import ClaimRequest, ClaimResponse, ClaimListResponse

router = APIRouter(tags=["Claims"])


@router.post("/claims/process", response_model=ClaimResponse)
async def process_claim(
    request: ClaimRequest,
    email: Optional[str] = None,
    phone: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process an insurance claim with AI-powered decision making
    
    This endpoint analyzes the claim against policy documents, performs fraud
    detection, and provides an explainable decision.
    
    - **claim_type**: Type of claim (medical, dental, vision, accident, property, other)
    - **amount**: Claim amount in USD
    - **description**: Detailed description of the incident or service
    - **incident_date**: Date when the incident occurred (YYYY-MM-DD)
    - **document_id**: Optional - specific policy document to check against
    - **email**: Optional - email address for claim decision notification
    - **phone**: Optional - phone number for SMS alerts
    """
    
    # Validate claim amount
    if request.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Claim amount must be greater than 0"
        )
    
    if request.amount > 1000000:  # $1M limit
        raise HTTPException(
            status_code=400,
            detail="Claim amount exceeds maximum limit of $1,000,000"
        )
    
    # Validate description
    if len(request.description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description must be at least 10 characters long"
        )
    
    try:
        # Convert request to dictionary
        claim_data = request.dict()
        
        # Process claim using the claim service
        result = await claim_service.process_claim(
            claim_data=claim_data,
            document_id=request.document_id
        )
        
        # Save claim to database
        try:
            claim_repo = get_claim_repo()
            
            # Prepare claim data for database
            claim_record = {**claim_data, **result}
            db_record_id = await claim_repo.save_claim(claim_record)
            result['database_record_id'] = db_record_id
            
        except Exception as e:
            print(f"Warning: Failed to save claim to database: {e}")
            result['database_record_id'] = None
        
        # Send notifications if contact info provided
        if email or phone:
            try:
                notification_data = {**claim_data, **result}
                notification_result = await notification_service.notify_claim_decision(
                    claim_data=notification_data,
                    email=email,
                    phone=phone
                )
                result['notification_sent'] = notification_result
                
            except Exception as e:
                print(f"Warning: Failed to send notifications: {e}")
                result['notification_sent'] = {
                    'success': False,
                    'error': str(e)
                }
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process claim: {str(e)}"
        )


@router.get("/claims", response_model=ClaimListResponse)
async def list_claims(
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    List processed claims with optional filtering
    
    - **limit**: Maximum number of claims to return (max 100)
    - **offset**: Number of claims to skip for pagination
    - **status_filter**: Filter by decision status (APPROVED, DENIED, REQUIRES_REVIEW)
    """
    
    if limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit cannot exceed 100"
        )
    
    if status_filter and status_filter not in ["APPROVED", "DENIED", "REQUIRES_REVIEW", "ERROR"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid status filter. Must be one of: APPROVED, DENIED, REQUIRES_REVIEW, ERROR"
        )
    
    try:
        claim_repo = get_claim_repo()
        claims = await claim_repo.list_claims(
            limit=limit,
            offset=offset,
            status_filter=status_filter
        )
        
        return {
            "claims": claims,
            "total": len(claims),
            "limit": limit,
            "offset": offset,
            "filter_applied": status_filter
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve claims: {str(e)}"
        )


@router.get("/claims/{claim_id}")
async def get_claim(claim_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific claim"""
    
    try:
        claim_repo = get_claim_repo()
        claim = await claim_repo.get_claim_by_id(claim_id)
        
        if not claim:
            raise HTTPException(
                status_code=404,
                detail="Claim not found"
            )
        
        return claim
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve claim: {str(e)}"
        )


@router.patch("/claims/{claim_id}/status")
async def update_claim_status(
    claim_id: str,
    status: str,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update claim status (for manual review outcomes)
    
    This endpoint is typically used by claims adjusters to update the
    final status of claims that required manual review.
    
    - **status**: New status (approved, denied, pending)
    - **notes**: Optional notes about the status change
    """
    
    valid_statuses = ["approved", "denied", "pending", "under_review"]
    if status.lower() not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    try:
        claim_repo = get_claim_repo()
        
        # Check if claim exists
        existing_claim = await claim_repo.get_claim_by_id(claim_id)
        if not existing_claim:
            raise HTTPException(
                status_code=404,
                detail="Claim not found"
            )
        
        # Update claim status
        updated = await claim_repo.update_claim_status(
            claim_id=claim_id,
            status=status.lower(),
            notes=notes
        )
        
        if not updated:
            raise HTTPException(
                status_code=500,
                detail="Failed to update claim status"
            )
        
        return {
            "success": True,
            "claim_id": claim_id,
            "new_status": status.lower(),
            "notes": notes,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update claim status: {str(e)}"
        )


@router.get("/claims/stats/summary")
async def get_claims_statistics() -> Dict[str, Any]:
    """Get claims processing statistics and analytics"""
    
    try:
        # Get database statistics
        try:
            claim_repo = get_claim_repo()
            db_stats = await claim_repo.get_claim_statistics()
        except Exception:
            db_stats = {"error": "Database unavailable"}
        
        # Get service statistics
        service_stats = claim_service.get_claim_statistics()
        
        return {
            "database_stats": db_stats,
            "service_stats": service_stats,
            "fraud_detection": {
                "enabled": True,
                "model_version": "1.0_rule_based",
                "features_used": [
                    "claim_amount",
                    "description_analysis", 
                    "timing_patterns",
                    "behavioral_indicators"
                ]
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.post("/claims/{claim_id}/reprocess")
async def reprocess_claim(claim_id: str) -> Dict[str, Any]:
    """
    Reprocess a claim with updated AI models or policy documents
    
    Useful when new policy documents are uploaded or AI models are updated.
    """
    
    try:
        claim_repo = get_claim_repo()
        
        # Get existing claim
        existing_claim = await claim_repo.get_claim_by_id(claim_id)
        if not existing_claim:
            raise HTTPException(
                status_code=404,
                detail="Claim not found"
            )
        
        # Extract original claim data
        original_claim_data = {
            "claim_type": existing_claim["claim_type"],
            "amount": existing_claim["amount"],
            "description": existing_claim["description"],
            "incident_date": existing_claim["incident_date"]
        }
        
        # Reprocess claim
        result = await claim_service.process_claim(
            claim_data=original_claim_data,
            document_id=existing_claim.get("document_id")
        )
        
        # Update database with new results
        update_data = {
            "decision": result["decision"],
            "explanation": result["explanation"],
            "fraud_score": result["fraud_score"],
            "fraud_risk_level": result["fraud_risk_level"],
            "fraud_indicators": result["fraud_indicators"],
            "ai_confidence": result["ai_confidence"],
            "policy_references": result["policy_references"],
            "processing_details": result["processing_details"],
            "reprocessed_at": datetime.utcnow().isoformat()
        }
        
        # Note: This would require extending the claim repository with an update method
        # For now, we'll return the new analysis
        
        return {
            "success": True,
            "claim_id": claim_id,
            "reprocessing_result": result,
            "original_decision": existing_claim["decision"],
            "new_decision": result["decision"],
            "decision_changed": existing_claim["decision"] != result["decision"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reprocess claim: {str(e)}"
        )