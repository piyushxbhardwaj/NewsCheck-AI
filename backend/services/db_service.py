import sqlite3
import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.config import settings

@contextmanager
def get_db():
    """Context manager for database connections, ensuring proper closing and foreign key support."""
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()

def init_db(schema_path: Optional[str] = None):
    """Initializes the database using the schema.sql script."""
    if not schema_path:
        from pathlib import Path
        schema_path = str(Path(__file__).resolve().parent.parent.parent / "database" / "schema.sql")
    
    with get_db() as conn:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()

def save_article(article: Dict[str, Any], claims: List[Dict[str, Any]], evidences: List[Dict[str, Any]]) -> str:
    """
    Saves an article, its claims, and the associated evidence in a single transaction.
    Returns the article ID.
    """
    article_id = article.get("id") or str(uuid.uuid4())
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # 1. Insert or Replace Article
            cursor.execute(
                """
                INSERT OR REPLACE INTO articles 
                (id, url, title, content, summary, verdict, credibility_score, bias_rating, tone_rating, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    article.get("url"),
                    article.get("title"),
                    article.get("content"),
                    article.get("summary"),
                    article.get("verdict"),
                    article.get("credibility_score"),
                    article.get("bias_rating"),
                    article.get("tone_rating"),
                    article.get("created_at", datetime.now().isoformat())
                )
            )

            # 2. Insert Claims
            for claim in claims:
                claim_id = claim.get("id") or str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO claims (id, article_id, claim_text, verdict, explanation)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        claim_id,
                        article_id,
                        claim.get("claim_text"),
                        claim.get("verdict"),
                        claim.get("explanation")
                    )
                )

                # 3. Insert Evidence for this claim
                # Filter evidences belonging to this specific claim
                claim_evidences = [e for e in evidences if e.get("claim_id") == claim.get("id") or e.get("claim_text") == claim.get("claim_text")]
                for ev in claim_evidences:
                    ev_id = ev.get("id") or str(uuid.uuid4())
                    
                    # Ensure source exists in sources table (or upsert a default/scraped one)
                    domain = ev.get("source_domain")
                    if domain:
                        cursor.execute(
                            "INSERT OR IGNORE INTO sources (domain, credibility_score, bias_rating) VALUES (?, ?, ?)",
                            (domain, 0.5, "Unknown")
                        )

                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO evidences (id, claim_id, source_domain, source_url, source_title, snippet, type, relevance_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ev_id,
                            claim_id,
                            domain,
                            ev.get("source_url"),
                            ev.get("source_title"),
                            ev.get("snippet"),
                            ev.get("type"),
                            ev.get("relevance_score")
                        )
                    )
            
            conn.commit()
            return article_id
        except Exception as e:
            conn.rollback()
            raise e

def get_articles_history() -> List[Dict[str, Any]]:
    """Retrieves all articles from the database sorted by creation time."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM articles ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_article_details(article_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves all details for a given article, including its claims and corresponding evidence."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Fetch article
        cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        article_row = cursor.fetchone()
        if not article_row:
            return None
        
        article = dict(article_row)
        
        # Fetch claims
        cursor.execute("SELECT * FROM claims WHERE article_id = ?", (article_id,))
        claims_rows = cursor.fetchall()
        claims = [dict(row) for row in claims_rows]
        
        # Fetch evidence for each claim
        for claim in claims:
            cursor.execute(
                """
                SELECT e.*, s.credibility_score as source_credibility, s.bias_rating as source_bias
                FROM evidences e
                LEFT JOIN sources s ON e.source_domain = s.domain
                WHERE e.claim_id = ?
                """, 
                (claim["id"],)
            )
            evidence_rows = cursor.fetchall()
            claim["evidences"] = [dict(row) for row in evidence_rows]
            
        article["claims"] = claims
        return article

def get_sources_dict() -> Dict[str, Dict[str, Any]]:
    """Loads all known sources for quick lookup in memory."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sources")
        rows = cursor.fetchall()
        return {row["domain"]: dict(row) for row in rows}

def upsert_source(domain: str, credibility_score: float, bias_rating: str, description: str = ""):
    """Adds or updates a source profile in the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO sources (domain, credibility_score, bias_rating, description)
            VALUES (?, ?, ?, ?)
            """,
            (domain, credibility_score, bias_rating, description)
        )
        conn.commit()
