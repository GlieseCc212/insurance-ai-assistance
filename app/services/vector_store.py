"""
Vector Database Service
Handles document embeddings storage and semantic search using ChromaDB
"""
import os
import uuid
from typing import List, Dict, Any, Optional, Tuple
import asyncio

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np

from ..config import get_settings

settings = get_settings()


class VectorStore:
    """Service for managing document embeddings and semantic search"""
    
    def __init__(self):
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        
        # Collection for storing document chunks
        self.collection_name = "insurance_documents"
        self.collection = self._get_or_create_collection()
    
    def _get_or_create_collection(self):
        """Get existing collection or create new one"""
        try:
            return self.client.get_collection(name=self.collection_name)
        except Exception:
            return self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Insurance policy document chunks"}
            )
    
    async def store_document_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Store document chunks with embeddings in ChromaDB
        
        Args:
            chunks: List of document chunks with content and metadata
            
        Returns:
            Dictionary with storage results
        """
        if not chunks:
            return {'stored_chunks': 0, 'error': 'No chunks provided'}
        
        # Prepare data for ChromaDB
        chunk_ids = []
        chunk_contents = []
        chunk_metadatas = []
        
        for chunk in chunks:
            chunk_ids.append(chunk['chunk_id'])
            chunk_contents.append(chunk['content'])
            
            # Prepare metadata (ChromaDB requires string values)
            metadata = {
                'document_id': chunk['document_id'],
                'chunk_index': str(chunk['chunk_index']),
                'content_length': str(len(chunk['content']))
            }
            
            # Add any additional metadata
            if 'metadata' in chunk and chunk['metadata']:
                for key, value in chunk['metadata'].items():
                    if isinstance(value, (str, int, float)):
                        metadata[f"meta_{key}"] = str(value)
            
            chunk_metadatas.append(metadata)
        
        try:
            # Generate embeddings
            embeddings = await self._generate_embeddings(chunk_contents)
            
            # Store in ChromaDB
            self.collection.add(
                documents=chunk_contents,
                embeddings=embeddings.tolist(),
                metadatas=chunk_metadatas,
                ids=chunk_ids
            )
            
            return {
                'stored_chunks': len(chunks),
                'collection_size': self.collection.count()
            }
            
        except Exception as e:
            return {
                'stored_chunks': 0,
                'error': f"Failed to store chunks: {str(e)}"
            }
    
    async def semantic_search(
        self, 
        query: str, 
        document_id: Optional[str] = None,
        top_k: int = 5,
        min_relevance_score: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search on stored documents
        
        Args:
            query: Search query
            document_id: Optional filter by specific document
            top_k: Number of results to return
            min_relevance_score: Minimum relevance threshold
            
        Returns:
            List of relevant document chunks with scores
        """
        try:
            # Generate query embedding
            query_embedding = await self._generate_embeddings([query])
            
            # Prepare search filters
            where_clause = {}
            if document_id:
                where_clause["document_id"] = document_id
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=top_k,
                where=where_clause if where_clause else None,
                include=['documents', 'metadatas', 'distances']
            )
            
            # Process results
            relevant_chunks = []
            if results['documents'] and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    # Convert distance to similarity score (lower distance = higher similarity)
                    similarity_score = max(0, 1 - distance)
                    
                    if similarity_score >= min_relevance_score:
                        relevant_chunks.append({
                            'content': doc,
                            'metadata': metadata,
                            'similarity_score': round(similarity_score, 4),
                            'rank': i + 1
                        })
            
            return relevant_chunks
            
        except Exception as e:
            print(f"Search error: {str(e)}")
            return []
    
    async def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document"""
        try:
            results = self.collection.get(
                where={"document_id": document_id},
                include=['documents', 'metadatas']
            )
            
            chunks = []
            if results['documents']:
                for doc, metadata in zip(results['documents'], results['metadatas']):
                    chunks.append({
                        'content': doc,
                        'metadata': metadata,
                        'chunk_index': int(metadata.get('chunk_index', 0))
                    })
                
                # Sort by chunk index
                chunks.sort(key=lambda x: x['chunk_index'])
            
            return chunks
            
        except Exception as e:
            print(f"Error retrieving document chunks: {str(e)}")
            return []
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete all chunks for a specific document"""
        try:
            # Get all chunk IDs for the document
            results = self.collection.get(
                where={"document_id": document_id},
                include=['metadatas']
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                return True
            
            return False
            
        except Exception as e:
            print(f"Error deleting document: {str(e)}")
            return False
    
    async def _generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts"""
        # Run embedding generation in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, 
            self.embedding_model.encode, 
            texts
        )
        return embeddings
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection"""
        try:
            count = self.collection.count()
            return {
                'total_chunks': count,
                'collection_name': self.collection_name,
                'embedding_model': settings.embedding_model
            }
        except Exception as e:
            return {
                'error': f"Failed to get stats: {str(e)}"
            }
    
    def list_documents(self) -> List[str]:
        """List all unique document IDs in the collection"""
        try:
            results = self.collection.get(include=['metadatas'])
            document_ids = set()
            
            for metadata in results['metadatas']:
                if 'document_id' in metadata:
                    document_ids.add(metadata['document_id'])
            
            return list(document_ids)
            
        except Exception as e:
            print(f"Error listing documents: {str(e)}")
            return []


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for insurance Q&A"""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
    
    async def retrieve_relevant_context(
        self, 
        query: str, 
        document_id: Optional[str] = None,
        max_context_length: int = 4000
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Retrieve relevant context for a query
        
        Args:
            query: User question
            document_id: Optional specific document to search
            max_context_length: Maximum length of combined context
            
        Returns:
            Tuple of (combined_context, relevant_chunks)
        """
        # Search for relevant chunks
        relevant_chunks = await self.vector_store.semantic_search(
            query=query,
            document_id=document_id,
            top_k=10,  # Get more chunks initially
            min_relevance_score=0.3
        )
        
        # Combine context while respecting length limit
        combined_context = ""
        selected_chunks = []
        current_length = 0
        
        for chunk in relevant_chunks:
            chunk_text = chunk['content']
            chunk_length = len(chunk_text)
            
            if current_length + chunk_length <= max_context_length:
                if combined_context:
                    combined_context += "\n\n---\n\n"
                combined_context += chunk_text
                current_length += chunk_length + 10  # Account for separator
                selected_chunks.append(chunk)
            else:
                break
        
        return combined_context, selected_chunks


# Global instances
vector_store = VectorStore()
rag_pipeline = RAGPipeline(vector_store)