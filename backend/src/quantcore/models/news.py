from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class News(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(primary_key=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )

    company = relationship(
        "Company",
        back_populates="news",
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    publisher: Mapped[str] = mapped_column(
        String(255),
    )

    summary: Mapped[str] = mapped_column(
        Text,
    )

    url: Mapped[str] = mapped_column(
        String(1000),
        unique=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


Index(
    "ix_news_company_date",
    News.company_id,
    News.published_at,
)