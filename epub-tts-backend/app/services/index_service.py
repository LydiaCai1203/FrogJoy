"""
Index Service —— Book Language Server 的索引构建和查询

职责:
  - build_index: 解析 EPUB → 落库 (IndexedBook + IndexedParagraph)
  - get_status: 查某书的索引状态
  - get_paragraphs: 按章节拉段落
  - delete_index: 删除索引 (重建前)

当前 v0 只实现段落层索引 (不做 LLM Extractor)。
concepts / occurrences / translations 等留给 Phase 1/2 LLM 接入后扩展。

设计文档:
  - docs/book-as-indexed-knowledge-base.md §5 (四层架构)
  - docs/translation-and-glossary-design.md §6 (实施路径 v0)
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.database import get_db
from app.models.models import Book, IndexedBook, IndexedParagraph
from app.parsers import EpubIndexParser


class IndexService:
    """
    所有方法都是类方法 / 静态方法, 保持和现有 BookService 风格一致。
    """

    # ---------- Build ----------

    @classmethod
    def build_index(
        cls,
        book_id: str,
        user_id: str,
        rebuild: bool = False,
    ) -> dict:
        """
        为某用户的某本书构建索引 (只做 Parser 层)。

        返回统计 dict。失败会抛 HTTPException 或把 error_message 写入 DB。

        参数:
          rebuild: True 时先删除旧索引再重新构建。
                   默认 False: 如果已 parsed 则直接返回现状。
        """
        # 前置检查: 书存在
        with get_db() as db:
            book = (
                db.query(Book)
                .filter(Book.id == book_id, Book.user_id == user_id)
                .first()
            )
            if not book:
                raise HTTPException(status_code=404, detail="Book not found")

            existing = (
                db.query(IndexedBook)
                .filter_by(book_id=book_id, user_id=user_id)
                .first()
            )

            if existing and existing.status == "parsed" and not rebuild:
                return cls._stats_from_existing(existing)

            if existing and rebuild:
                cls._delete_paragraphs(db, book_id, user_id)
                db.delete(existing)
                db.commit()

            # 标记 parsing 状态
            indexed = IndexedBook(
                book_id=book_id,
                user_id=user_id,
                book_fingerprint="",
                status="parsing",
                index_version="v0",
            )
            db.add(indexed)
            db.commit()

        # 解析 EPUB (可能耗时, 脱离 db 事务)
        epub_path = settings.get_book_path(user_id, book_id)
        try:
            parser = EpubIndexParser(epub_path)
            parsed = parser.parse()
        except Exception as e:
            logger.exception(f"Failed to parse EPUB: book={book_id} user={user_id}")
            with get_db() as db:
                record = (
                    db.query(IndexedBook)
                    .filter_by(book_id=book_id, user_id=user_id)
                    .first()
                )
                if record:
                    record.status = "failed"
                    record.error_message = f"parse_failed: {e}"
                    db.commit()
            raise HTTPException(status_code=500,
                                detail=f"Failed to parse EPUB: {e}")

        # 落库
        try:
            with get_db() as db:
                record = (
                    db.query(IndexedBook)
                    .filter_by(book_id=book_id, user_id=user_id)
                    .first()
                )
                if not record:
                    raise RuntimeError("IndexedBook record vanished")

                record.book_fingerprint = parsed.book_fingerprint
                record.total_chapters = len(parsed.chapters)
                record.total_paragraphs = parsed.total_paragraphs
                record.parsed_at = datetime.utcnow()
                record.status = "parsed"
                record.error_message = None

                # 批量写 paragraphs
                # 注: EPUB 里偶有重复段落 (如 "好的" 在同章多次),
                # 虽然我们 prev_text 消歧, 但保险起见用 set 去重
                seen_pids = set()
                rows = []
                for chapter in parsed.chapters:
                    for p in chapter.paragraphs:
                        if p.pid in seen_pids:
                            logger.warning(
                                f"Duplicate pid within book: {p.pid} "
                                f"book={book_id} ch{p.chapter_idx}:p{p.para_idx_in_chapter}"
                            )
                            continue
                        seen_pids.add(p.pid)
                        rows.append({
                            "id": p.pid,
                            "user_id": user_id,
                            "book_id": book_id,
                            "chapter_idx": chapter.idx,
                            "chapter_title": chapter.title,
                            "chapter_fp": chapter.chapter_fp,
                            "para_idx_in_chapter": p.para_idx_in_chapter,
                            "text": p.text,
                        })

                if rows:
                    db.bulk_insert_mappings(IndexedParagraph, rows)
                db.commit()

                logger.info(
                    f"Built index: book={book_id} user={user_id} "
                    f"chapters={record.total_chapters} "
                    f"paragraphs={record.total_paragraphs}"
                )
                return cls._stats_from_existing(record)

        except Exception as e:
            logger.exception(f"Failed to persist index: book={book_id} user={user_id}")
            with get_db() as db:
                record = (
                    db.query(IndexedBook)
                    .filter_by(book_id=book_id, user_id=user_id)
                    .first()
                )
                if record:
                    record.status = "failed"
                    record.error_message = f"persist_failed: {e}"
                    db.commit()
            raise HTTPException(status_code=500,
                                detail=f"Failed to persist index: {e}")

    # ---------- Query ----------

    @classmethod
    def get_status(cls, book_id: str, user_id: str) -> dict | None:
        with get_db() as db:
            record = (
                db.query(IndexedBook)
                .filter_by(book_id=book_id, user_id=user_id)
                .first()
            )
            return cls._stats_from_existing(record) if record else None

    @classmethod
    def get_paragraphs(
        cls,
        book_id: str,
        user_id: str,
        chapter_idx: int | None = None,
    ) -> list[dict]:
        """
        拉段落列表。指定 chapter_idx 只拉该章。
        结果按 (chapter_idx, para_idx_in_chapter) 升序。
        """
        with get_db() as db:
            q = (
                db.query(IndexedParagraph)
                .filter_by(book_id=book_id, user_id=user_id)
            )
            if chapter_idx is not None:
                q = q.filter(IndexedParagraph.chapter_idx == chapter_idx)
            q = q.order_by(
                IndexedParagraph.chapter_idx,
                IndexedParagraph.para_idx_in_chapter,
            )
            return [
                {
                    "pid": p.id,
                    "chapter_idx": p.chapter_idx,
                    "chapter_title": p.chapter_title,
                    "chapter_fp": p.chapter_fp,
                    "para_idx": p.para_idx_in_chapter,
                    "text": p.text,
                }
                for p in q.all()
            ]

    @classmethod
    def get_chapters(cls, book_id: str, user_id: str) -> list[dict]:
        """
        返回章节概要: (idx, title, chapter_fp, paragraph_count)。
        UI 渲染章节目录用。
        """
        with get_db() as db:
            # 一次 group by 聚合
            from sqlalchemy import func
            rows = (
                db.query(
                    IndexedParagraph.chapter_idx,
                    IndexedParagraph.chapter_title,
                    IndexedParagraph.chapter_fp,
                    func.count(IndexedParagraph.id).label("count"),
                )
                .filter_by(book_id=book_id, user_id=user_id)
                .group_by(
                    IndexedParagraph.chapter_idx,
                    IndexedParagraph.chapter_title,
                    IndexedParagraph.chapter_fp,
                )
                .order_by(IndexedParagraph.chapter_idx)
                .all()
            )
            return [
                {
                    "chapter_idx": r.chapter_idx,
                    "chapter_title": r.chapter_title,
                    "chapter_fp": r.chapter_fp,
                    "paragraph_count": r.count,
                }
                for r in rows
            ]

    # ---------- Delete ----------

    @classmethod
    def delete_index(cls, book_id: str, user_id: str) -> bool:
        """完全删除某书索引 (IndexedBook + paragraphs)。用于重建或退还。"""
        with get_db() as db:
            cls._delete_paragraphs(db, book_id, user_id)
            deleted = (
                db.query(IndexedBook)
                .filter_by(book_id=book_id, user_id=user_id)
                .delete()
            )
            db.commit()
            return deleted > 0

    # ---------- Internals ----------

    @staticmethod
    def _delete_paragraphs(db: Session, book_id: str, user_id: str) -> int:
        return (
            db.query(IndexedParagraph)
            .filter_by(book_id=book_id, user_id=user_id)
            .delete()
        )

    @staticmethod
    def _stats_from_existing(record: IndexedBook) -> dict:
        return {
            "book_id": record.book_id,
            "user_id": record.user_id,
            "book_fingerprint": record.book_fingerprint,
            "total_chapters": record.total_chapters,
            "total_paragraphs": record.total_paragraphs,
            "status": record.status,
            "error_message": record.error_message,
            "index_version": record.index_version,
            "parsed_at": record.parsed_at.isoformat() if record.parsed_at else None,
        }
