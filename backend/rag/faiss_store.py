from typing import List, Dict, Any, Tuple, Optional
import logging
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from backend.config import settings

logger = logging.getLogger(__name__)

def get_embeddings():
    """Initializes and returns the configured embedding model."""
    # Handle custom api base and key (e.g. for LocalAI/LM Studio/Ollama)
    api_key = settings.openai_api_key or "placeholder_key"
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=api_key,
        openai_api_base=settings.openai_api_base
    )

def build_vector_store(search_results: List[Dict[str, Any]]) -> Optional[FAISS]:
    """
    Builds an in-memory FAISS vector store from search results.
    Each search result is treated as a document to be indexed.
    """
    if not search_results:
        logger.warning("No search results to index in FAISS.")
        return None
        
    documents = []
    for idx, result in enumerate(search_results):
        snippet = result.get("snippet", "")
        if not snippet:
            continue
            
        # Add metadata to track where the information came from
        metadata = {
            "source_url": result.get("url", ""),
            "source_title": result.get("title", ""),
            "source_domain": result.get("domain", ""),
            "index": idx
        }
        
        # We can also chunk larger snippets if necessary. For standard search snippets, 
        # they are already short (1-2 sentences), so we index them directly.
        documents.append(Document(page_content=snippet, metadata=metadata))
        
    if not documents:
        return None
        
    try:
        embeddings = get_embeddings()
        vector_store = FAISS.from_documents(documents, embeddings)
        logger.info(f"Successfully created FAISS vector store with {len(documents)} documents.")
        return vector_store
    except Exception as e:
        logger.error(f"Failed to create FAISS vector store: {e}")
        return None

def retrieve_relevant_evidence(vector_store: FAISS, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Queries the FAISS index to find the most relevant snippets for a given claim.
    Returns a list of dicts containing the content, source URL, title, and similarity score.
    """
    if not vector_store:
        return []
        
    try:
        # Perform similarity search with score
        results_with_scores: List[Tuple[Document, float]] = vector_store.similarity_search_with_relevance_scores(query, k=top_k)
        
        evidence = []
        for doc, score in results_with_scores:
            evidence.append({
                "snippet": doc.page_content,
                "source_url": doc.metadata.get("source_url", ""),
                "source_title": doc.metadata.get("source_title", ""),
                "source_domain": doc.metadata.get("source_domain", ""),
                "relevance_score": float(score)
            })
        return evidence
    except Exception as e:
        logger.error(f"Error retrieving evidence from FAISS: {e}")
        return []
