"""
Database connection and models for MongoDB
Handles data persistence for users, documents, and claims
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import IndexModel
from bson import ObjectId
import logging

from .config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class MongoDB:
    """MongoDB connection manager"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self.is_connected = False
    
    async def connect(self):
        """Connect to MongoDB database"""
        try:
            self.client = AsyncIOMotorClient(settings.mongodb_url)
            self.database = self.client[settings.mongodb_db_name]
            
            # Test connection
            await self.client.admin.command('ping')
            self.is_connected = True
            
            # Create indexes
            await self._create_indexes()
            
            logger.info(f"Connected to MongoDB database: {settings.mongodb_db_name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            self.is_connected = False
            raise
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info("Disconnected from MongoDB")
    
    async def _create_indexes(self):
        """Create database indexes for optimal performance"""
        if not self.database:
            return
        
        # Documents collection indexes
        documents_indexes = [
            IndexModel("document_id"),
            IndexModel("upload_timestamp"),
            IndexModel("policy_type"),
            IndexModel([("upload_timestamp", -1)])  # Descending order for recent documents
        ]
        await self.database.documents.create_indexes(documents_indexes)
        
        # Claims collection indexes
        claims_indexes = [
            IndexModel("claim_id"),
            IndexModel("document_id"),
            IndexModel("status"),
            IndexModel("created_at"),
            IndexModel([("created_at", -1)]),  # Recent claims first
            IndexModel([("status", 1), ("created_at", -1)])  # Filter by status, sort by date
        ]
        await self.database.claims.create_indexes(claims_indexes)
        
        # Users collection indexes (if user management is added later)
        users_indexes = [
            IndexModel("user_id"),
            IndexModel("email", unique=True),
            IndexModel("created_at")
        ]
        await self.database.users.create_indexes(users_indexes)
        
        logger.info("Database indexes created successfully")


class DocumentRepository:
    """Repository for document-related database operations"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.db = database
        self.collection = database.documents
    
    async def save_document(self, document_data: Dict[str, Any]) -> str:
        """Save document metadata to database"""
        document_record = {
            "document_id": document_data["document_id"],
            "filename": document_data["filename"],
            "file_type": document_data["file_type"],
            "policy_type": document_data.get("policy_type"),
            "text_length": document_data["text_length"],
            "pages_processed": document_data["pages_processed"],
            "chunks_created": document_data["chunks_created"],
            "processing_time": document_data["processing_time"],
            "metadata": document_data.get("metadata", {}),
            "upload_timestamp": datetime.utcnow(),
            "status": "processed"
        }
        
        result = await self.collection.insert_one(document_record)
        return str(result.inserted_id)
    
    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve document by document_id"""
        document = await self.collection.find_one({"document_id": document_id})
        if document:
            document["_id"] = str(document["_id"])
        return document
    
    async def list_documents(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List all documents with pagination"""
        cursor = self.collection.find().sort("upload_timestamp", -1).skip(offset).limit(limit)
        documents = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            documents.append(doc)
        
        return documents
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete document from database"""
        result = await self.collection.delete_one({"document_id": document_id})
        return result.deleted_count > 0
    
    async def get_document_stats(self) -> Dict[str, Any]:
        """Get document statistics"""
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_documents": {"$sum": 1},
                    "total_pages": {"$sum": "$pages_processed"},
                    "total_chunks": {"$sum": "$chunks_created"},
                    "avg_processing_time": {"$avg": "$processing_time"}
                }
            }
        ]
        
        result = await self.collection.aggregate(pipeline).to_list(1)
        if result:
            stats = result[0]
            stats.pop("_id", None)
            return stats
        
        return {
            "total_documents": 0,
            "total_pages": 0,
            "total_chunks": 0,
            "avg_processing_time": 0.0
        }


class ClaimRepository:
    """Repository for claim-related database operations"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.db = database
        self.collection = database.claims
    
    async def save_claim(self, claim_data: Dict[str, Any]) -> str:
        """Save claim record to database"""
        claim_record = {
            "claim_id": claim_data["claim_id"],
            "document_id": claim_data.get("document_id"),
            "claim_type": claim_data.get("claim_type"),
            "amount": claim_data.get("amount"),
            "description": claim_data.get("description"),
            "incident_date": claim_data.get("incident_date"),
            "decision": claim_data["decision"],
            "explanation": claim_data["explanation"],
            "fraud_score": claim_data.get("fraud_score", 0.0),
            "fraud_risk_level": claim_data.get("fraud_risk_level", "UNKNOWN"),
            "fraud_indicators": claim_data.get("fraud_indicators", []),
            "ai_confidence": claim_data.get("ai_confidence", 0.0),
            "policy_references": claim_data.get("policy_references", []),
            "processing_details": claim_data.get("processing_details", {}),
            "status": "processed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(claim_record)
        return str(result.inserted_id)
    
    async def get_claim_by_id(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve claim by claim_id"""
        claim = await self.collection.find_one({"claim_id": claim_id})
        if claim:
            claim["_id"] = str(claim["_id"])
        return claim
    
    async def list_claims(
        self, 
        limit: int = 50, 
        offset: int = 0, 
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List claims with optional filtering"""
        query = {}
        if status_filter:
            query["decision"] = status_filter
        
        cursor = self.collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
        claims = []
        
        async for claim in cursor:
            claim["_id"] = str(claim["_id"])
            claims.append(claim)
        
        return claims
    
    async def update_claim_status(self, claim_id: str, status: str, notes: Optional[str] = None) -> bool:
        """Update claim status (for manual review outcomes)"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if notes:
            update_data["manual_review_notes"] = notes
        
        result = await self.collection.update_one(
            {"claim_id": claim_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def get_claim_statistics(self) -> Dict[str, Any]:
        """Get claim processing statistics"""
        pipeline = [
            {
                "$group": {
                    "_id": "$decision",
                    "count": {"$sum": 1},
                    "avg_amount": {"$avg": "$amount"},
                    "avg_fraud_score": {"$avg": "$fraud_score"},
                    "avg_ai_confidence": {"$avg": "$ai_confidence"}
                }
            }
        ]
        
        results = await self.collection.aggregate(pipeline).to_list(10)
        
        stats = {
            "total_claims": 0,
            "approved": 0,
            "denied": 0,
            "requires_review": 0,
            "error": 0,
            "avg_processing_metrics": {}
        }
        
        for result in results:
            decision = result["_id"].lower().replace(" ", "_")
            count = result["count"]
            
            stats["total_claims"] += count
            
            if decision == "approved":
                stats["approved"] = count
            elif decision == "denied":
                stats["denied"] = count
            elif decision in ["requires_review", "requires review"]:
                stats["requires_review"] = count
            elif decision == "error":
                stats["error"] = count
            
            stats["avg_processing_metrics"][decision] = {
                "avg_amount": round(result.get("avg_amount", 0), 2),
                "avg_fraud_score": round(result.get("avg_fraud_score", 0), 4),
                "avg_ai_confidence": round(result.get("avg_ai_confidence", 0), 4)
            }
        
        return stats


# Global database manager and repositories
mongodb = MongoDB()
document_repo: Optional[DocumentRepository] = None
claim_repo: Optional[ClaimRepository] = None


async def init_db():
    """Initialize database connection and repositories"""
    global document_repo, claim_repo
    
    try:
        await mongodb.connect()
        
        if mongodb.database:
            document_repo = DocumentRepository(mongodb.database)
            claim_repo = ClaimRepository(mongodb.database)
            
            logger.info("Database repositories initialized successfully")
        else:
            logger.error("Database connection failed - repositories not initialized")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        # Don't raise the exception to allow the app to start without DB
        # In production, you might want to handle this differently


async def close_db():
    """Close database connection"""
    await mongodb.disconnect()


def get_db() -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    if not mongodb.database:
        raise RuntimeError("Database not initialized")
    return mongodb.database


def get_document_repo() -> DocumentRepository:
    """Get document repository instance"""
    if not document_repo:
        raise RuntimeError("Document repository not initialized")
    return document_repo


def get_claim_repo() -> ClaimRepository:
    """Get claim repository instance"""
    if not claim_repo:
        raise RuntimeError("Claim repository not initialized")
    return claim_repo