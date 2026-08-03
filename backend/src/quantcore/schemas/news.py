from datetime import datetime

from pydantic import BaseModel


class NewsData(BaseModel):
    title: str
    publisher: str
    summary: str
    url: str
    published_at: datetime | None = None