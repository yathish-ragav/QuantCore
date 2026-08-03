from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsArticle:
    title: str
    publisher: str
    summary: str
    url: str
    published_at: datetime | None    
    