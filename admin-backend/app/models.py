"""
ORM models — mirrors the main backend's models.
This admin service connects to the same database, so models must match exactly.
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime, ForeignKey, Index,
    UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False, server_default="false")
    is_admin = Column(Boolean, default=False, server_default="false")
    is_active = Column(Boolean, default=True, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
    last_login_at = Column(DateTime, nullable=True)

    books = relationship("Book", back_populates="user")
    reading_stats = relationship("ReadingStat", back_populates="user")


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
    reading_stats = relationship("ReadingStat", back_populates="book")

    __table_args__ = (
        Index("idx_books_user_id", "user_id"),
        Index("idx_books_is_public", "is_public"),
    )


class ReadingStat(Base):
    __tablename__ = "reading_stats"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    date = Column(String, nullable=False)
    duration_seconds = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="reading_stats")
    book = relationship("Book", back_populates="reading_stats")

    __table_args__ = (
        UniqueConstraint("user_id", "book_id", "date", name="uq_reading_stats_user_book_date"),
        Index("idx_reading_stats_user_date", "user_id", "date"),
        Index("idx_reading_stats_user_book", "user_id", "book_id"),
    )


class Highlight(Base):
    __tablename__ = "highlights"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    chapter_href = Column(String, nullable=False)
    selected_text = Column(Text, nullable=False)
    color = Column(String, nullable=False, default="yellow")
    note = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_highlights_book_chapter", "book_id", "chapter_href"),
        Index("idx_highlights_user_book", "user_id", "book_id"),
    )


class SystemSetting(Base):
    """System-wide settings managed via admin panel"""
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
