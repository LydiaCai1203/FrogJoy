from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from shared.models import Base


class IndexedBook(Base):
    """
    每用户每本书的索引元信息。

    一本书对应 Book 表里一条记录, 其"索引状态"挂在这张表上:
      - 还没扫?  不在此表
      - 扫过?    status='parsed', 可以查询 paragraphs
      - 扫失败?  status='failed', 看 error_message

    后续 Extractor (LLM) 会往此表加 extractor_status 字段。
    """
    __tablename__ = "indexed_books"

    book_id = Column(String, ForeignKey("books.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)

    # 书的稳定指纹 (来自 paragraph_id.book_id), 用于跨书识别同一部作品
    book_fingerprint = Column(String, nullable=False)

    # 统计
    total_chapters = Column(Integer, nullable=False, default=0)
    total_paragraphs = Column(Integer, nullable=False, default=0)

    # 状态: pending / parsing / parsed / failed
    status = Column(String, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)

    # 索引版本 (schema 演进)
    index_version = Column(String, nullable=False, default="v0")

    # 时间戳
    parsed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    book = relationship("Book")

    __table_args__ = (
        Index("idx_indexed_books_user", "user_id"),
        Index("idx_indexed_books_fingerprint", "book_fingerprint"),
    )


class IndexedParagraph(Base):
    """
    段落级索引条目。

    id = paragraph_id (见 app/parsers/paragraph_id.py)
      格式: {book_id}:{chapter_fp}:{content_fp}
      稳定、确定性, 同一段落不同次解析产生相同 id。

    每用户每本书的段落是独立行 (因 Book 本身是 per-user 的)。
    未来若要跨用户去重, 可在 book_fingerprint 层聚合。
    """
    __tablename__ = "indexed_paragraphs"

    id = Column(String, primary_key=True)                                    # paragraph_id
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)

    # 章节
    chapter_idx = Column(Integer, nullable=False)
    chapter_title = Column(String, nullable=True)
    chapter_fp = Column(String, nullable=False)

    # 章内位置
    para_idx_in_chapter = Column(Integer, nullable=False)

    # 内容 (原文)
    text = Column(Text, nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # 主要查询模式: 按 (user, book) 拉段落, 或 (user, book, chapter)
        Index("idx_iparagraphs_user_book", "user_id", "book_id"),
        Index("idx_iparagraphs_user_book_chapter",
              "user_id", "book_id", "chapter_idx"),
    )
