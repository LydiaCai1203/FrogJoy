"""
端到端测试: Index Layer

不启 FastAPI, 直接:
  1. 用一个临时 SQLite DB
  2. 跑 migration
  3. 直接调 IndexService.build_index
  4. 验证数据落库
  5. 验证查询

运行:
  DATABASE_URL="sqlite:////tmp/test_index.db" \
    ./venv/bin/python test_index_e2e.py
"""
import os
import shutil
import sys
import uuid
from pathlib import Path

TEST_EPUB = "/Users/caiqj/Downloads/无条件养育/无条件养育.epub"
TEST_DB = "/tmp/test_index.db"
BACKEND_DIR = Path(__file__).parent

# 临时屏蔽 .env (里面的 DATABASE_URL 会覆盖我们的)
_ORIG_ENV = BACKEND_DIR / ".env"
_BACKUP_ENV = BACKEND_DIR / ".env.e2e_backup"
if _ORIG_ENV.exists():
    _ORIG_ENV.rename(_BACKUP_ENV)

import atexit
@atexit.register
def _restore_env():
    if _BACKUP_ENV.exists():
        _BACKUP_ENV.rename(_ORIG_ENV)

# Set env BEFORE any app imports
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["FERNET_KEY"] = "VGVzdEtleUZvckVuY3J5cHRpb24xMjM0NTY3ODlBQkNERUY="


def reset_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    from alembic.config import Config
    from alembic import command
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


def setup_test_book() -> tuple[str, str]:
    """把测试 epub 复制到 data/users/<user_id>/<book_id>/book.epub"""
    from app.config import settings
    from app.models.database import get_db
    from app.models.models import User, Book
    from datetime import datetime

    user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    book_id = f"test-book-{uuid.uuid4().hex[:8]}"

    # 准备用户
    with get_db() as db:
        user = User(
            id=user_id,
            email=f"{user_id}@test.local",
            password_hash="x",
        )
        db.add(user)

        book = Book(
            id=book_id,
            user_id=user_id,
            title="test",
            creator="test",
            file_path="book.epub",
        )
        db.add(book)
        db.commit()

    # 复制 epub
    book_dir = settings.get_user_book_dir(user_id, book_id)
    os.makedirs(book_dir, exist_ok=True)
    shutil.copy(TEST_EPUB, settings.get_book_path(user_id, book_id))

    return user_id, book_id


def main():
    print("=" * 60)
    print("Reset DB + run migrations")
    print("=" * 60)
    reset_db()
    print("  ✓ DB ready")

    user_id, book_id = setup_test_book()
    print(f"  user_id = {user_id}")
    print(f"  book_id = {book_id}")

    print()
    print("=" * 60)
    print("Build index")
    print("=" * 60)
    from app.services.index_service import IndexService
    result = IndexService.build_index(book_id=book_id, user_id=user_id)
    print(f"  status:           {result['status']}")
    print(f"  book_fingerprint: {result['book_fingerprint']}")
    print(f"  total_chapters:   {result['total_chapters']}")
    print(f"  total_paragraphs: {result['total_paragraphs']}")
    assert result["status"] == "parsed"
    assert result["total_paragraphs"] > 1000

    print()
    print("=" * 60)
    print("Check idempotency (second call should be no-op)")
    print("=" * 60)
    result2 = IndexService.build_index(book_id=book_id, user_id=user_id)
    assert result2["total_paragraphs"] == result["total_paragraphs"]
    print("  ✓ idempotent")

    print()
    print("=" * 60)
    print("Query chapters")
    print("=" * 60)
    chapters = IndexService.get_chapters(book_id, user_id)
    print(f"  章节数: {len(chapters)}")
    for c in chapters[:5]:
        title = (c["chapter_title"] or "[无]")[:30]
        print(f"    [{c['chapter_idx']:02d}] {title:<32} | {c['paragraph_count']} 段")
    print(f"    ... 还有 {len(chapters) - 5} 章")

    print()
    print("=" * 60)
    print("Query one chapter's paragraphs")
    print("=" * 60)
    # 找"第一章"所在章节
    first_ch_idx = None
    for c in chapters:
        if c["chapter_title"] and "第一章" in c["chapter_title"]:
            first_ch_idx = c["chapter_idx"]
            break
    if first_ch_idx is not None:
        paras = IndexService.get_paragraphs(book_id, user_id, chapter_idx=first_ch_idx)
        print(f"  第一章 ({first_ch_idx}): {len(paras)} 段")
        for p in paras[:2]:
            print(f"    [{p['para_idx']:03d}] pid={p['pid']}")
            print(f"          text={p['text'][:50]}...")
    else:
        print("  (没找到'第一章', 跳过)")

    print()
    print("=" * 60)
    print("Delete index")
    print("=" * 60)
    deleted = IndexService.delete_index(book_id, user_id)
    assert deleted
    status_after = IndexService.get_status(book_id, user_id)
    assert status_after is None
    print("  ✓ deleted")

    print()
    print("=" * 60)
    print("Rebuild after delete")
    print("=" * 60)
    result3 = IndexService.build_index(book_id=book_id, user_id=user_id)
    assert result3["total_paragraphs"] == result["total_paragraphs"]
    print(f"  ✓ rebuild OK, {result3['total_paragraphs']} paragraphs")

    # paragraph_id 稳定性验证
    print()
    print("=" * 60)
    print("Stability: paragraph_id 两次 build 是否一致")
    print("=" * 60)
    first_run_paras = IndexService.get_paragraphs(book_id, user_id)
    IndexService.delete_index(book_id, user_id)
    IndexService.build_index(book_id=book_id, user_id=user_id)
    second_run_paras = IndexService.get_paragraphs(book_id, user_id)

    first_ids = sorted(p["pid"] for p in first_run_paras)
    second_ids = sorted(p["pid"] for p in second_run_paras)
    assert first_ids == second_ids
    print(f"  ✓ 两次构建产生相同的 {len(first_ids)} 个 paragraph_id")

    print()
    print("=" * 60)
    print("✓ ALL E2E TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main() or 0)
