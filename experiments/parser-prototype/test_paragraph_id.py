"""
paragraph_id 测试矩阵
对应设计文档 §8 测试场景
"""
import sys
from paragraph_id import (
    BookMeta,
    book_id,
    chapter_fp,
    content_fp,
    normalize_paragraph,
    paragraph_id,
)


META = BookMeta(title="Test Book", author="Test Author", isbn="9780000000001")


def run_test(name: str, cond: bool, detail: str = ""):
    status = "✓" if cond else "✗"
    print(f"  {status} {name}")
    if not cond and detail:
        print(f"    {detail}")
    return cond


def main():
    results = []

    print("\n--- 1. 确定性 ---")
    pid1 = paragraph_id(META, "Ch 1", 0, 5, "Hello world")
    pid2 = paragraph_id(META, "Ch 1", 0, 5, "Hello world")
    results.append(run_test(
        "同输入 → 同 ID",
        pid1 == pid2,
        f"pid1={pid1}\n    pid2={pid2}",
    ))

    print("\n--- 2. 空白不变性 ---")
    pid1 = paragraph_id(META, "Ch 1", 0, 5, "Hello  world")
    pid2 = paragraph_id(META, "Ch 1", 0, 5, "Hello world")
    results.append(run_test("多空白归一后相同", pid1 == pid2))

    print("\n--- 3. 大小写敏感 (保护专有名词) ---")
    pid1 = paragraph_id(META, "Ch 1", 0, 5, "MIT is a school")
    pid2 = paragraph_id(META, "Ch 1", 0, 5, "mit is a school")
    results.append(run_test("大小写不同 → ID 不同", pid1 != pid2))

    print("\n--- 4. 相同内容不同位置消歧 ---")
    pid1 = paragraph_id(META, "Ch 1", 0, 5, "同样的话")
    pid2 = paragraph_id(META, "Ch 1", 0, 9, "同样的话")
    results.append(run_test("位置不同 → ID 不同", pid1 != pid2))

    print("\n--- 5. 不同章节消歧 ---")
    pid1 = paragraph_id(META, "Ch 1", 0, 5, "Hello")
    pid2 = paragraph_id(META, "Ch 2", 1, 5, "Hello")
    results.append(run_test("不同章节 → ID 不同", pid1 != pid2))

    print("\n--- 6. 章节顺序变 (重排) 不影响 chapter_fp ---")
    fp_a = chapter_fp("body", 1)
    fp_b = chapter_fp("body", 2)
    results.append(run_test("同标题不同 idx → chapter_fp 相同", fp_a == fp_b))

    print("\n--- 7. ISBN 相同 → book_id 相同 ---")
    m1 = BookMeta("X", "Y", "9780000000001")
    m2 = BookMeta("X", "Y", "9780000000001")
    results.append(run_test("同 ISBN → book_id 相同", book_id(m1) == book_id(m2)))

    print("\n--- 8. 无 ISBN 退化签名 ---")
    m1 = BookMeta("X", "Y")
    m2 = BookMeta("X", "Y")
    bid = book_id(m1)
    results.append(run_test(
        "无 ISBN 同作者标题 → 同 book_id",
        book_id(m1) == book_id(m2) and bid.startswith("sig:"),
        f"bid={bid}",
    ))

    print("\n--- 9. 短段落用前文补强 ---")
    pid1 = paragraph_id(META, "Ch 1", 0, 5, "是。", prev_text="你去吗？")
    pid2 = paragraph_id(META, "Ch 1", 0, 5, "是。", prev_text="你确定？")
    results.append(run_test(
        "短段落 + 不同前文 → ID 不同",
        pid1 != pid2,
        f"pid1={pid1}\n    pid2={pid2}",
    ))

    print("\n--- 10. 章节序号前缀剥离 ---")
    fp_a = chapter_fp("Chapter 3: Introduction", 2)
    fp_b = chapter_fp("3. Introduction", 2)
    fp_c = chapter_fp("Introduction", 2)
    results.append(run_test(
        "英文 / 数字 / 裸标题 → 同 chapter_fp",
        fp_a == fp_b == fp_c,
        f"英文={fp_a} 数字={fp_b} 裸={fp_c}",
    ))

    fp_zh_a = chapter_fp("第三章 启发式", 2)
    fp_zh_b = chapter_fp("3. 启发式", 2)
    fp_zh_c = chapter_fp("启发式", 2)
    results.append(run_test(
        "中文章节序号剥离",
        fp_zh_a == fp_zh_b == fp_zh_c,
        f"中文={fp_zh_a} 数字={fp_zh_b} 裸={fp_zh_c}",
    ))

    print("\n--- 11. 无标题章节退化 ---")
    fp1 = chapter_fp(None, 5)
    fp2 = chapter_fp("", 5)
    fp3 = chapter_fp(None, 10)
    results.append(run_test(
        "无标题 → idx 退化, 不同 idx 不同 fp",
        fp1 == fp2 and fp1 != fp3,
        f"fp1={fp1} fp2={fp2} fp3={fp3}",
    ))

    print("\n--- 12. ID 格式 ---")
    pid = paragraph_id(META, "Ch 1", 0, 5, "Hello world")
    parts = pid.split(":")
    results.append(run_test(
        "ID 是三段式 (book:chapter:content)",
        len(parts) == 3 and parts[0].startswith("isbn:") is False and pid.startswith("isbn:"),
        f"pid={pid} 段数={len(parts)}",
    ))
    # 注: ISBN 里本身带 ':', 所以 len(parts) = 4 也可能是合法的
    # 重新检查：
    prefix, _, rest = pid.partition(":")
    parts_after_book = rest.split(":")
    results.append(run_test(
        "book_id + chapter_fp + content_fp",
        prefix in ("isbn", "sig") and len(parts_after_book) == 3,
        f"pid={pid}",
    ))

    passed = sum(results)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"测试结果: {passed}/{total} passed")
    print(f"{'='*50}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
