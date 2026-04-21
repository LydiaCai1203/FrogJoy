from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from shared.models import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    creator = Column(String)
    cover_url = Column(String)
    file_path = Column(String, nullable=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    last_opened_at = Column(DateTime)

    user = relationship("User", back_populates="books")
    highlights = relationship("Highlight", back_populates="book", cascade="all, delete-orphan")
    reading_stats = relationship("ReadingStat", back_populates="book", cascade="all, delete-orphan")
    reading_progress = relationship("ReadingProgress", back_populates="book", cascade="all, delete-orphan")
    book_translations = relationship("BookTranslation", back_populates="book", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_books_user_id", "user_id"),
        Index("idx_books_is_public", "is_public"),
    )
