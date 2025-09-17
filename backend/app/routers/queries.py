"""
Queries Router
Handles policy questions and AI-powered responses
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ..services.ai_service import ai_service
from ..models.schemas import QueryRequest, QueryResponse

router = APIRouter(tags=["Queries"])


@router.post("/queries/ask", response_model=QueryResponse)
async def ask_policy_question(request: QueryRequest) -> Dict[str, Any]:
    """
    Ask a question about insurance policy documents
    
    Uses RAG (Retrieval-Augmented Generation) to find relevant policy clauses
    and provide accurate answers with references.
    
    - **query**: Your question about the policy in natural language
    - **document_id**: Optional - search within a specific document
    """
    
    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )
    
    try:
        # Process query using AI service
        result = await ai_service.answer_policy_question(
            query=request.query,
            document_id=request.document_id
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )


@router.post("/queries/search")
async def semantic_search(request: QueryRequest, top_k: int = 5) -> Dict[str, Any]:
    """
    Perform semantic search across policy documents
    
    Returns the most relevant document chunks without AI interpretation.
    Useful for finding specific clauses or sections.
    
    - **query**: Search terms or question
    - **document_id**: Optional - search within a specific document  
    - **top_k**: Number of results to return (max 20)
    """
    
    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )
    
    if top_k > 20:
        raise HTTPException(
            status_code=400,
            detail="top_k cannot exceed 20"
        )
    
    try:
        from ..services.vector_store import vector_store
        
        # Perform semantic search
        results = await vector_store.semantic_search(
            query=request.query,
            document_id=request.document_id,
            top_k=top_k,
            min_relevance_score=0.2
        )
        
        return {
            "query": request.query,
            "document_id": request.document_id,
            "results_count": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/queries/suggestions")
async def get_query_suggestions() -> Dict[str, Any]:
    """
    Get suggested questions that users commonly ask about insurance policies
    
    Helpful for guiding users on what types of questions they can ask.
    """
    
    suggestions = [
        {
            "category": "Coverage",
            "questions": [
                "What is covered under my health insurance policy?",
                "Is emergency room treatment covered?",
                "What is my deductible amount?",
                "Are prescription medications covered?",
                "What is the coverage limit for dental procedures?"
            ]
        },
        {
            "category": "Claims",
            "questions": [
                "How do I file a claim?",
                "What documents are needed for a claim?",
                "How long does claim processing take?",
                "What is the claim approval process?",
                "Can I appeal a denied claim?"
            ]
        },
        {
            "category": "Exclusions",
            "questions": [
                "What is not covered by my policy?",
                "Are pre-existing conditions excluded?",
                "What are the policy exclusions?",
                "Is cosmetic surgery covered?",
                "Are experimental treatments covered?"
            ]
        },
        {
            "category": "Policy Details",
            "questions": [
                "When does my policy expire?",
                "What is my policy number?",
                "How do I update my policy information?",
                "What are the renewal terms?",
                "Can I cancel my policy?"
            ]
        }
    ]
    
    return {
        "suggestions": suggestions,
        "total_categories": len(suggestions),
        "total_questions": sum(len(cat["questions"]) for cat in suggestions)
    }