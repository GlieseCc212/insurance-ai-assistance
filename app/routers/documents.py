"""
Documents Router
Handles document upload, processing, and management
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Dict, Any, List, Optional
import asyncio

from ..services.document_processor import document_processor
from ..services.vector_store import vector_store
from ..services.notification_service import notification_service
from ..database import get_document_repo
from ..models.schemas import DocumentResponse, DocumentListResponse
from ..config import get_settings

settings = get_settings()

router = APIRouter(tags=["Documents"])


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    policy_type: Optional[str] = Form(None),
    email: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """
    Upload and process insurance policy document
    
    - **file**: PDF or DOCX file containing insurance policy
    - **policy_type**: Type of insurance policy (health, auto, home, life, other)
    - **email**: Optional email for processing notifications
    """
    
    # Validate file
    if not document_processor.validate_file_type(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported types: {document_processor.get_supported_file_types()}"
        )
    
    # Read file content
    file_content = await file.read()
    
    if not document_processor.validate_file_size(len(file_content)):
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_file_size / (1024*1024):.1f}MB"
        )
    
    try:
        # Process document
        processing_result = await document_processor.process_document(
            file_content=file_content,
            filename=file.filename,
            policy_type=policy_type
        )
        
        # Store document chunks in vector database
        vector_result = await vector_store.store_document_chunks(
            processing_result['chunks']
        )
        
        # Save document metadata to database
        try:
            document_repo = get_document_repo()
            db_record_id = await document_repo.save_document(processing_result)
        except Exception as e:
            # Continue even if database save fails
            print(f"Warning: Failed to save document to database: {e}")
            db_record_id = None
        
        # Send notification if email provided
        if email:
            try:
                await notification_service.notify_document_processed(
                    document_data=processing_result,
                    email=email
                )
            except Exception as e:
                print(f"Warning: Failed to send notification: {e}")
        
        return {
            "success": True,
            "document_id": processing_result['document_id'],
            "filename": processing_result['filename'],
            "pages_processed": processing_result['pages_processed'],
            "chunks_created": processing_result['chunks_created'],
            "processing_time": processing_result['processing_time'],
            "vector_storage": vector_result,
            "database_record_id": db_record_id
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """List uploaded documents with pagination"""
    
    try:
        document_repo = get_document_repo()
        documents = await document_repo.list_documents(limit=limit, offset=offset)
        
        return {
            "documents": documents,
            "total": len(documents),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve documents: {str(e)}")


@router.get("/documents/{document_id}")
async def get_document(document_id: str) -> Dict[str, Any]:
    """Get document details by ID"""
    
    try:
        document_repo = get_document_repo()
        document = await document_repo.get_document_by_id(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve document: {str(e)}")


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str) -> Dict[str, Any]:
    """Delete document and associated data"""
    
    try:
        # Delete from vector store
        vector_deleted = await vector_store.delete_document(document_id)
        
        # Delete from database
        try:
            document_repo = get_document_repo()
            db_deleted = await document_repo.delete_document(document_id)
        except Exception as e:
            print(f"Warning: Failed to delete from database: {e}")
            db_deleted = False
        
        if not vector_deleted and not db_deleted:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "success": True,
            "document_id": document_id,
            "vector_deleted": vector_deleted,
            "database_deleted": db_deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@router.get("/documents/{document_id}/chunks")
async def get_document_chunks(document_id: str) -> Dict[str, Any]:
    """Get all text chunks for a document"""
    
    try:
        chunks = await vector_store.get_document_chunks(document_id)
        
        if not chunks:
            raise HTTPException(status_code=404, detail="Document or chunks not found")
        
        return {
            "document_id": document_id,
            "total_chunks": len(chunks),
            "chunks": chunks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chunks: {str(e)}")


@router.get("/documents/stats/summary")
async def get_document_stats() -> Dict[str, Any]:
    """Get document processing statistics"""
    
    try:
        # Get database stats
        try:
            document_repo = get_document_repo()
            db_stats = await document_repo.get_document_stats()
        except Exception:
            db_stats = {"error": "Database unavailable"}
        
        # Get vector store stats
        try:
            vector_stats = vector_store.get_collection_stats()
        except Exception:
            vector_stats = {"error": "Vector store unavailable"}
        
        return {
            "database": db_stats,
            "vector_store": vector_stats,
            "supported_formats": document_processor.get_supported_file_types()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")