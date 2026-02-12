"""Search: ILIKE (default) or FTS (tsvector). Feature-flagged via config."""
from sqlalchemy import Select, cast, Text, text

from app.db.models import Item
from app.core.config import get_settings


def apply_search_filter(query: Select, q: str) -> Select:
    """Apply search filter to items query. q is non-empty stripped string."""
    settings = get_settings()
    term = f"%{q}%"
    if settings.search_backend == "fts":
        # FTS: items.search_tsv (migration 004). Bind param avoids injection.
        query = query.where(
            text("items.search_tsv @@ plainto_tsquery('english', :q)").bindparams(q=q)
        )
        return query
    # ILIKE
    query = query.where(
        (Item.title.ilike(term))
        | (Item.summary.ilike(term))
        | (cast(Item.payload, Text).ilike(term))
    )
    return query
