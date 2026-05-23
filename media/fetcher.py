"""
Fetcher RSS — récupère les articles des 7 derniers jours
depuis les gros médias football français et internationaux.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

FEEDS: list[tuple[str, str]] = [
    # ── Médias FR (testés fonctionnels) ──────────────────────────────────────
    ("RMC Sport",      "https://rmcsport.bfmtv.com/rss/football/"),
    ("FootActu",       "https://footactu.fr/feed/"),
    ("Transfermarkt",  "https://www.transfermarkt.fr/rss/news"),
    ("But Football",   "https://www.butfootballclub.fr/feed/"),
    ("France24 Sport", "https://www.france24.com/fr/sports/rss"),
    # ── Sources INT football (couverture Big 5) ───────────────────────────────
    ("BBC Sport",      "https://feeds.bbci.co.uk/sport/football/rss.xml"),
    ("Sky Sports",     "https://www.skysports.com/rss/12040"),
    ("ESPN FC",        "https://www.espn.com/espn/rss/soccer/news"),
]


def _parse_date(entry) -> Optional[datetime]:
    """Extrait la date d'une entrée feedparser."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _clean_summary(raw: str, max_chars: int = 350) -> str:
    """Retire les balises HTML basiques et tronque."""
    import re
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def fetch_articles(days: int = 7) -> tuple[list[dict], list[str]]:
    """
    Récupère tous les articles des `days` derniers jours depuis les feeds RSS.
    Retourne (articles, errors).
    articles = liste de dicts {source, title, summary, date, url}.
    """
    try:
        import feedparser
    except ImportError:
        return [], ["Package 'feedparser' non installé. Lancer : pip install feedparser"]

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    articles: list[dict] = []
    errors: list[str] = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url, request_headers=headers)
            status = getattr(feed, "status", 0)
            if status == 404:
                errors.append(f"{source}: HTTP 404")
                continue

            for entry in feed.entries:
                published = _parse_date(entry)

                # Si article trop vieux, on skip (mais on garde ceux sans date)
                if published and published < cutoff:
                    continue

                title   = (getattr(entry, "title",   "") or "").strip()
                summary = _clean_summary(getattr(entry, "summary", "") or "")
                link    = getattr(entry, "link", "")
                date_str = published.strftime("%Y-%m-%d") if published else "N/A"

                if not title:
                    continue

                articles.append({
                    "source":  source,
                    "title":   title,
                    "summary": summary,
                    "date":    date_str,
                    "url":     link,
                })

        except Exception as e:
            errors.append(f"{source}: {e}")

    # Tri antéchronologique
    articles.sort(key=lambda a: a["date"], reverse=True)
    return articles, errors
