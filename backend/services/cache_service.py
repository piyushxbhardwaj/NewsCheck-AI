from datetime import datetime, timedelta
import json
from typing import Any, Optional
from backend.services.db_service import get_db
from backend.config import settings

def _clean_expired_cache(cursor):
    """Deletes expired entries from the cache."""
    now = datetime.now().isoformat()
    cursor.execute("DELETE FROM cache WHERE expiry_time < ?", (now,))

def get_cached(key: str) -> Optional[Any]:
    """Retrieves a value from the cache if it exists and has not expired."""
    with get_db() as conn:
        cursor = conn.cursor()
        _clean_expired_cache(cursor)
        
        cursor.execute("SELECT cache_value FROM cache WHERE cache_key = ?", (key,))
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row["cache_value"])
            except json.JSONDecodeError:
                return row["cache_value"]
    return None

def set_cached(key: str, value: Any, expiry_hours: Optional[int] = None) -> None:
    """Stores a value in the cache with a specified expiration time."""
    if expiry_hours is None:
        expiry_hours = settings.cache_expiry_hours
        
    value_str = json.dumps(value)
    expiry_time = (datetime.now() + timedelta(hours=expiry_hours)).isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        _clean_expired_cache(cursor)
        
        cursor.execute(
            """
            INSERT OR REPLACE INTO cache (cache_key, cache_value, expiry_time)
            VALUES (?, ?, ?)
            """,
            (key, value_str, expiry_time)
        )
        conn.commit()
