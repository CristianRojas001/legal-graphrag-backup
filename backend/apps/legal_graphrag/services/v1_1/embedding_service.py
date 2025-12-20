"""
Embedding Service - Generates vector embeddings using Gemini API
"""

import google.generativeai as genai
from django.conf import settings
from typing import List
import logging
import time

logger = logging.getLogger('apps.legal_graphrag.ingestion')


class EmbeddingService:
    """
    Generates embeddings using Gemini text-embedding-004

    Specs:
    - Model: text-embedding-004
    - Dimensions: 768
    - Max input: 2048 tokens (~8000 chars)
    - Rate limit: 1500 requests/day (free tier)
    """

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_name = 'models/text-embedding-004'

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for text

        Args:
            text: Input text (max 8000 chars recommended)

        Returns:
            List of 768 floats
        """
        # Truncate if too long
        if len(text) > 8000:
            logger.warning(f"Text truncated from {len(text)} to 8000 chars")
            text = text[:8000]

        try:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document"  # Optimize for retrieval
            )

            return result['embedding']

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def embed_batch(self, texts: List[str], delay_ms: int = 100) -> List[List[float]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of input texts
            delay_ms: Delay between requests (rate limiting)

        Returns:
            List of embeddings
        """
        embeddings = []

        for idx, text in enumerate(texts):
            logger.info(f"Embedding chunk {idx + 1}/{len(texts)}")

            embedding = self.embed(text)
            embeddings.append(embedding)

            # Rate limiting
            if idx < len(texts) - 1:
                time.sleep(delay_ms / 1000)

        return embeddings
