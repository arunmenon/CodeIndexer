"""
Embedding Tool

Tool for generating vector embeddings from code text.
"""

import os
import logging
import time
import numpy as np
from typing import Dict, List, Any, Optional, Union

from google.adk.tooling import BaseTool

# Try to import different embedding libraries
HAS_SENTENCE_TRANSFORMERS = False
HAS_OPENAI = False
HAS_VERTEX_AI = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    logging.warning("SentenceTransformers not available. Install sentence-transformers package to use it.")

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    logging.warning("OpenAI package not available. Install openai package to use it.")

try:
    from google.cloud import aiplatform
    HAS_VERTEX_AI = True
except ImportError:
    logging.warning("Google Vertex AI not available. Install google-cloud-aiplatform to use it.")


class EmbeddingTool(BaseTool):
    """
    Tool for generating embeddings from code text.
    
    Provides functionality to create vector embeddings for code snippets,
    supporting multiple backend models.
    """
    
    def __init__(self):
        """Initialize the Embedding Tool."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Default settings
        self.model_type = os.environ.get("EMBEDDING_MODEL_TYPE", "sentence_transformers")
        self.model_name = os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
        
        # Initialize the embedding model
        self.model = None
        self.initialize_model()
    
    def initialize_model(self) -> bool:
        """
        Initialize the embedding model based on configuration.
        
        Returns:
            True if initialization succeeded, False otherwise
        """
        if self.model_type == "sentence_transformers":
            return self._init_sentence_transformers()
        elif self.model_type == "openai":
            return self._init_openai()
        elif self.model_type == "vertex_ai":
            return self._init_vertex_ai()
        else:
            self.logger.error(f"Unsupported model type: {self.model_type}")
            return False
    
    def _init_sentence_transformers(self) -> bool:
        """
        Initialize a SentenceTransformers model.
        
        Returns:
            True if initialization succeeded, False otherwise
        """
        if not HAS_SENTENCE_TRANSFORMERS:
            self.logger.error("SentenceTransformers not available")
            return False
        
        try:
            self.model = SentenceTransformer(self.model_name)
            self.logger.info(f"Initialized SentenceTransformers model: {self.model_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing SentenceTransformers model: {e}")
            return False
    
    def _init_openai(self) -> bool:
        """
        Initialize OpenAI API access.
        
        Returns:
            True if initialization succeeded, False otherwise
        """
        if not HAS_OPENAI:
            self.logger.error("OpenAI package not available")
            return False
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            self.logger.error("OPENAI_API_KEY environment variable not set")
            return False
        
        try:
            openai.api_key = api_key
            self.model_name = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
            self.logger.info(f"Initialized OpenAI API with model: {self.model_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing OpenAI API: {e}")
            return False
    
    def _init_vertex_ai(self) -> bool:
        """
        Initialize Google Vertex AI access.
        
        Returns:
            True if initialization succeeded, False otherwise
        """
        if not HAS_VERTEX_AI:
            self.logger.error("Google Vertex AI not available")
            return False
        
        try:
            aiplatform.init()
            self.model_name = os.environ.get("VERTEX_AI_EMBEDDING_MODEL", "textembedding-gecko")
            self.logger.info(f"Initialized Vertex AI with model: {self.model_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing Vertex AI: {e}")
            return False
    
    def embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
            
        Raises:
            Exception: If embedding generation fails
        """
        if not texts:
            return []
        
        if self.model_type == "sentence_transformers":
            return self._embed_with_sentence_transformers(texts)
        elif self.model_type == "openai":
            return self._embed_with_openai(texts)
        elif self.model_type == "vertex_ai":
            return self._embed_with_vertex_ai(texts)
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")
    
    def _embed_with_sentence_transformers(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings using SentenceTransformers.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not self.model:
            self._init_sentence_transformers()
            if not self.model:
                raise ValueError("SentenceTransformers model initialization failed")
        
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings
    
    def _embed_with_openai(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings using OpenAI API.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not HAS_OPENAI or not openai.api_key:
            raise ValueError("OpenAI API not properly initialized")
        
        # Process in batches to avoid rate limits
        batch_size = 16  # OpenAI recommends small batches
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            try:
                response = openai.Embedding.create(
                    model=self.model_name,
                    input=batch
                )
                
                # Extract embeddings from response
                batch_embeddings = [
                    np.array(item["embedding"]) 
                    for item in response["data"]
                ]
                all_embeddings.extend(batch_embeddings)
                
                # Sleep briefly to avoid rate limits
                if i + batch_size < len(texts):
                    time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error generating OpenAI embeddings: {e}")
                raise
        
        return all_embeddings
    
    def _embed_with_vertex_ai(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings using Google Vertex AI.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not HAS_VERTEX_AI:
            raise ValueError("Vertex AI not properly initialized")
        
        try:
            # Get the embedding model
            model = aiplatform.TextEmbeddingModel.from_pretrained(self.model_name)
            
            # Generate embeddings
            embeddings = model.get_embeddings(texts)
            
            # Extract and convert to numpy arrays
            return [np.array(emb.values) for emb in embeddings]
            
        except Exception as e:
            self.logger.error(f"Error generating Vertex AI embeddings: {e}")
            raise
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text string to embed
            
        Returns:
            Embedding vector
            
        Raises:
            Exception: If embedding generation fails
        """
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else None