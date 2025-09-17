"""
Health Check Router
Provides system health and status endpoints
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any
from datetime import datetime

from ..database import mongodb, get_document_repo, get_claim_repo
from ..services.vector_store import vector_store
from ..services.notification_service import notification_service

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "service": "Insurance AI Assistant"
    }


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check with service status"""
    
    # Check database connection
    db_status = {
        "connected": mongodb.is_connected,
        "database": mongodb.database.name if mongodb.database else None
    }
    
    # Check vector store
    try:
        vector_stats = vector_store.get_collection_stats()
        vector_status = {
            "available": True,
            "stats": vector_stats
        }
    except Exception as e:
        vector_status = {
            "available": False,
            "error": str(e)
        }
    
    # Check notification services
    notification_status = notification_service.get_service_status()
    
    # Overall health determination
    is_healthy = (
        db_status["connected"] and
        vector_status["available"]
    )
    
    return {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": {
            "database": db_status,
            "vector_store": vector_status,
            "notifications": notification_status
        }
    }


@router.get("/health/stats")
async def system_stats() -> Dict[str, Any]:
    """Get system statistics"""
    
    stats = {
        "documents": {"error": "Service unavailable"},
        "claims": {"error": "Service unavailable"},
        "vector_store": {"error": "Service unavailable"}
    }
    
    try:
        # Document statistics
        if mongodb.is_connected:
            document_repo = get_document_repo()
            claim_repo = get_claim_repo()
            
            stats["documents"] = await document_repo.get_document_stats()
            stats["claims"] = await claim_repo.get_claim_statistics()
    except Exception as e:
        stats["database_error"] = str(e)
    
    try:
        # Vector store statistics
        stats["vector_store"] = vector_store.get_collection_stats()
    except Exception as e:
        stats["vector_store"] = {"error": str(e)}
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "statistics": stats
    }