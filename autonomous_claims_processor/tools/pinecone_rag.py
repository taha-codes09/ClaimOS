"""
Pinecone RAG Tool
=================
Vector database integration for policy documents and historical claims.
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import hashlib
import json
from loguru import logger

try:
    from pinecone import Pinecone, ServerlessSpec
    from pinecone_text.sparse import BM25Encoder
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    Pinecone = None

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from ..core.settings import settings


class PineconeRAG:
    """
    Vector database operations for policy RAG and historical claims search.
    """
    
    def __init__(self):
        self.logger = logger.bind(module="pinecone_rag")
        self.client = None
        self.index = None
        self.embedder = None
        self.initialized = False
        
        self.index_name = settings.pinecone_index_name
        self.api_key = settings.pinecone_api_key
        self.environment = settings.pinecone_environment
    
    def initialize(self) -> bool:
        """Initialize Pinecone connection and index."""
        if not PINECONE_AVAILABLE:
            self.logger.warning("Pinecone client not available")
            return False
        
        if not self.api_key:
            self.logger.warning("Pinecone API key not configured")
            return False
        
        try:
            # Initialize client
            self.client = Pinecone(api_key=self.api_key)
            
            # List existing indexes
            existing_indexes = self.client.list_indexes().names()
            
            # Create index if not exists
            if self.index_name not in existing_indexes:
                self.logger.info(f"Creating index: {self.index_name}")
                self.client.create_index(
                    name=self.index_name,
                    dimension=384,  # all-MiniLM-L6-v2 dimension
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=self.environment
                    )
                )
            
            # Connect to index
            self.index = self.client.Index(self.index_name)
            
            # Initialize embedder
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            else:
                self.logger.warning("Sentence transformers not available")
            
            self.initialized = True
            self.logger.info("Pinecone RAG initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Pinecone initialization error: {str(e)}")
            return False
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if not self.embedder:
            # Fallback: simple hash-based embedding (not semantic)
            return self._fallback_embedding(text)
        
        return self.embedder.encode(text).tolist()
    
    def _fallback_embedding(self, text: str) -> List[float]:
        """Fallback embedding using text hashing."""
        # Simple 384-dim vector based on text hash
        hash_bytes = hashlib.md5(text.encode()).digest()
        embedding = list(hash_bytes) * 24  # 16 * 24 = 384
        return [x / 255.0 for x in embedding]  # Normalize to 0-1
    
    # ============================================================
    # POLICY DOCUMENT OPERATIONS
    # ============================================================
    
    def index_policy(
        self,
        policy_number: str,
        policy_form: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Index a policy document chunk.
        
        Args:
            policy_number: Policy number
            policy_form: Policy form number (ISO form)
            content: Text content to index
            metadata: Additional metadata
            
        Returns:
            Vector ID
        """
        if not self.initialized:
            if not self.initialize():
                return None
        
        # Generate vector ID
        vector_id = self._generate_policy_vector_id(policy_number, content)
        
        # Generate embedding
        embedding = self.embed_text(content)
        
        # Prepare metadata
        vector_metadata = {
            "type": "policy",
            "policy_number": policy_number,
            "policy_form": policy_form,
            "indexed_at": datetime.utcnow().isoformat(),
            **(metadata or {})
        }
        
        # Upsert to Pinecone
        try:
            self.index.upsert(
                vectors=[(vector_id, embedding, vector_metadata)],
                namespace="policies"
            )
            self.logger.info(f"Indexed policy chunk: {policy_number}")
            return vector_id
        except Exception as e:
            self.logger.error(f"Error indexing policy: {str(e)}")
            return None
    
    def index_policy_chunks(
        self,
        policy_number: str,
        policy_form: str,
        full_text: str,
        chunk_size: int = 256,
        chunk_overlap: int = 50
    ) -> List[str]:
        """
        Index full policy document in chunks.
        
        Args:
            policy_number: Policy number
            policy_form: Policy form number
            full_text: Complete policy text
            chunk_size: Tokens per chunk
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of vector IDs
        """
        # Split into chunks
        chunks = self._chunk_text(full_text, chunk_size, chunk_overlap)
        
        vector_ids = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "chunk_index": i,
                "total_chunks": len(chunks)
            }
            vector_id = self.index_policy(
                policy_number,
                policy_form,
                chunk,
                metadata
            )
            if vector_id:
                vector_ids.append(vector_id)
        
        return vector_ids
    
    def search_policies(
        self,
        query: str,
        policy_number: str = None,
        top_k: int = 5,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search policy documents.
        
        Args:
            query: Search query
            policy_number: Optional policy number to filter
            top_k: Number of results
            filters: Additional metadata filters
            
        Returns:
            List of matching chunks with scores
        """
        if not self.initialized:
            if not self.initialize():
                return []
        
        # Generate query embedding
        query_embedding = self.embed_text(query)
        
        # Build filter
        filter_expr = {"type": "policy"}
        if policy_number:
            filter_expr["policy_number"] = policy_number
        if filters:
            filter_expr.update(filters)
        
        # Search
        try:
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                filter=filter_expr,
                namespace="policies",
                include_metadata=True,
                include_values=False
            )
            
            return [
                {
                    "id": match.id,
                    "score": match.score,
                    "policy_number": match.metadata.get("policy_number"),
                    "policy_form": match.metadata.get("policy_form"),
                    "chunk_index": match.metadata.get("chunk_index"),
                    "content": match.metadata.get("content", "")
                }
                for match in results.matches
            ]
        except Exception as e:
            self.logger.error(f"Error searching policies: {str(e)}")
            return []
    
    # ============================================================
    # HISTORICAL CLAIMS OPERATIONS
    # ============================================================
    
    def index_historical_claim(
        self,
        claim_id: str,
        claim_summary: str,
        outcome: str,
        fraud_confirmed: bool = False,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Index a historical claim for similarity search.
        
        Args:
            claim_id: Claim ID
            claim_summary: Summary of claim facts
            outcome: Claim outcome (PAID, DENIED, SETTLED)
            fraud_confirmed: Whether fraud was confirmed
            metadata: Additional metadata
            
        Returns:
            Vector ID
        """
        if not self.initialized:
            if not self.initialize():
                return None
        
        vector_id = f"claim-{claim_id}"
        embedding = self.embed_text(claim_summary)
        
        vector_metadata = {
            "type": "historical_claim",
            "claim_id": claim_id,
            "outcome": outcome,
            "fraud_confirmed": fraud_confirmed,
            "indexed_at": datetime.utcnow().isoformat(),
            **(metadata or {})
        }
        
        try:
            self.index.upsert(
                vectors=[(vector_id, embedding, vector_metadata)],
                namespace="historical_claims"
            )
            return vector_id
        except Exception as e:
            self.logger.error(f"Error indexing historical claim: {str(e)}")
            return None
    
    def search_similar_claims(
        self,
        claim_summary: str,
        top_k: int = 5,
        fraud_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for similar historical claims.
        
        Args:
            claim_summary: Summary of current claim
            top_k: Number of results
            fraud_only: Only return fraud-confirmed claims
            
        Returns:
            List of similar claims
        """
        if not self.initialized:
            if not self.initialize():
                return []
        
        query_embedding = self.embed_text(claim_summary)
        
        filter_expr = {"type": "historical_claim"}
        if fraud_only:
            filter_expr["fraud_confirmed"] = True
        
        try:
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                filter=filter_expr,
                namespace="historical_claims",
                include_metadata=True,
                include_values=False
            )
            
            return [
                {
                    "claim_id": match.metadata.get("claim_id"),
                    "similarity_score": match.score,
                    "outcome": match.metadata.get("outcome"),
                    "fraud_confirmed": match.metadata.get("fraud_confirmed"),
                    "summary": match.metadata.get("claim_summary", "")
                }
                for match in results.matches
            ]
        except Exception as e:
            self.logger.error(f"Error searching similar claims: {str(e)}")
            return []
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        
        i = 0
        while i < len(words):
            chunk = words[i:i + chunk_size]
            chunks.append(" ".join(chunk))
            i += chunk_size - overlap
        
        return chunks
    
    def _generate_policy_vector_id(self, policy_number: str, content: str) -> str:
        """Generate unique vector ID for policy chunk."""
        data = f"{policy_number}_{content[:100]}_{datetime.utcnow().isoformat()}"
        return "pol-" + hashlib.md5(data.encode()).hexdigest()[:20]
    
    def delete_policy_vectors(self, policy_number: str) -> bool:
        """Delete all vectors for a policy."""
        if not self.initialized:
            return False
        
        try:
            # Delete by filter
            self.index.delete(filter={"policy_number": policy_number}, namespace="policies")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting policy vectors: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        if not self.initialized:
            return {"initialized": False}
        
        try:
            stats = self.index.describe_index_stats()
            return {
                "initialized": True,
                "total_vectors": stats.get("total_vector_count", 0),
                "namespaces": stats.get("namespaces", {})
            }
        except Exception as e:
            return {"initialized": False, "error": str(e)}


# Singleton instance
_pinecone_rag = None

def get_pinecone_rag() -> PineconeRAG:
    """Get or create Pinecone RAG singleton."""
    global _pinecone_rag
    if _pinecone_rag is None:
        _pinecone_rag = PineconeRAG()
    return _pinecone_rag
