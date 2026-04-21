from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from shared.models import Base


class Highlight(Base):
    __tablename__ = "highlights"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    chapter_href = Column(String, nullable=False)
    paragraph_index = Column(Integer, nullable=False, default=0)
    end_paragraph_index = Column(Integer, nullable=False, default=0)
    start_offset = Column(Integer, nullable=False, default=0)
    end_offset = Column(Integer, nullable=False, default=0)
    selected_text = Column(Text, nullable=False)
    color = Column(String, nullable=False, default="yellow")
    note = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="highlights")
    book = relationship("Book", back_populates="highlights")

    __table_args__ = (
        Index("idx_highlights_book_chapter", "book_id", "chapter_href"),
        Index("idx_highlights_user_book", "user_id", "book_id"),
    )
