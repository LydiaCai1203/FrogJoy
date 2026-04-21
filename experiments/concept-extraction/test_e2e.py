"""
概念提取端到端测试脚本

测试内容:
  1. 登录获取 token
  2. 检查书籍索引状态
  3. 触发概念提取 (POST /concepts/build)
  4. 轮询状态直到 enriched
  5. 检查概念列表 (GET /concepts)
  6. 检查角标数据 (GET /concepts/by-chapter/{idx})
"""

import time
import httpx

# --- 配置 ---
BASE_URL = "https://deepkb.com.cn/api"
EMAIL = "acaicai1203@gmail.com"
PASSWORD = "1234567890"
BOOK_ID = "d4604c94-bd82-4ecc-ae91-285a5775415d"

client = httpx.Client(timeout=60, verify=True)


def login():
    print("=" * 60)
    print("Step 1: 登录")
    print("=" * 60)
    resp = client.post(f"{BASE_URL}/auth/login", json={
        "email": EMAIL,
        "password": PASSWORD,
    })
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print(f"  Token: {token[:20]}...")
    client.headers["Authorization"] = f"Bearer {token}"
    return token


def check_index_status():
    print("\n" + "=" * 60)
    print("Step 2: 检查书籍索引状态")
    print("=" * 60)
    resp = client.get(f"{BASE_URL}/books/{BOOK_ID}/index/status")
    resp.raise_for_status()
    data = resp.json()
    print(f"  Index status: {data.get('status')}")
    print(f"  Chapters: {data.get('total_chapters')}")
    print(f"  Paragraphs: {data.get('total_paragraphs')}")
    if data.get("status") != "parsed":
        print("  !! Index not ready, cannot proceed")
        return False
    return True


def trigger_build():
    print("\n" + "=" * 60)
    print("Step 3: 触发概念提取")
    print("=" * 60)
    resp = client.post(f"{BASE_URL}/books/{BOOK_ID}/concepts/build")
    resp.raise_for_status()
    data = resp.json()
    print(f"  Response: {data}")
    return data


def poll_status(max_wait=300):
    print("\n" + "=" * 60)
    print("Step 4: 轮询概念提取状态")
    print("=" * 60)
    start = time.time()
    while time.time() - start < max_wait:
        resp = client.get(f"{BASE_URL}/books/{BOOK_ID}/concepts/status")
        resp.raise_for_status()
        data = resp.json()
        status = data.get("concept_status")
        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] concept_status={status}")

        if status == "enriched":
            print(f"  Concepts: {data.get('total_concepts')}")
            return True
        elif status == "failed":
            print(f"  ERROR: {data.get('concept_error')}")
            return False

        time.sleep(5)

    print(f"  Timeout after {max_wait}s")
    return False


def check_concepts():
    print("\n" + "=" * 60)
    print("Step 5: 检查概念列表")
    print("=" * 60)
    resp = client.get(f"{BASE_URL}/books/{BOOK_ID}/concepts")
    resp.raise_for_status()
    data = resp.json()
    concepts = data.get("concepts", [])
    print(f"  总概念数: {len(concepts)}")
    print()

    for c in concepts:
        aliases = ", ".join(c["aliases"]) if c["aliases"] else "-"
        print(f"  {c['term']}")
        print(f"    类型: {c['category']}  |  出现: {c['total_occurrences']}次  |  "
              f"跨{c['chapter_count']}章  |  scope: {c['scope']}")
        print(f"    别名: {aliases}")
        print()

    return concepts


def check_chapter_annotations(concepts):
    print("\n" + "=" * 60)
    print("Step 6: 检查角标数据 (第一章)")
    print("=" * 60)

    # 先找第一个有段落的章节
    resp = client.get(f"{BASE_URL}/books/{BOOK_ID}/index/chapters")
    resp.raise_for_status()
    chapters = resp.json().get("chapters", [])
    if not chapters:
        print("  No chapters found")
        return

    # 取前两个章节测试
    for chapter in chapters[:2]:
        chapter_idx = chapter["chapter_idx"]
        print(f"\n  --- 章节 {chapter_idx}: {chapter['chapter_title']} ---")

        resp = client.get(
            f"{BASE_URL}/books/{BOOK_ID}/concepts/by-chapter/{chapter_idx}"
        )
        resp.raise_for_status()
        data = resp.json()
        annotations = data.get("annotations", [])
        print(f"  角标数: {len(annotations)}")

        for ann in annotations:
            print(f"\n  ① {ann['term']}  (badge #{ann['badge_number']})")
            print(f"    首次出现段落: {ann['first_pid_in_chapter']}")
            popover = ann.get("popover", {})
            explanations = popover.get("explanations", [])
            print(f"    弹窗解释数: {len(explanations)}")
            for exp in explanations:
                sentence = exp.get("core_sentence", "")
                if sentence:
                    # 截取前 80 字展示
                    display = sentence[:80] + ("..." if len(sentence) > 80 else "")
                    print(f"    「{display}」")
                    print(f"      —— ch{exp['chapter_idx']}")


def check_concept_detail(concepts):
    print("\n" + "=" * 60)
    print("Step 7: 检查单个概念详情")
    print("=" * 60)
    if not concepts:
        print("  No concepts to check")
        return

    # 取第一个概念
    concept_id = concepts[0]["concept_id"]
    print(f"  查询: {concepts[0]['term']} ({concept_id})")

    resp = client.get(f"{BASE_URL}/books/{BOOK_ID}/concepts/{concept_id}")
    resp.raise_for_status()
    data = resp.json()

    occs = data.get("occurrences", [])
    print(f"  Occurrences: {len(occs)}")

    # 按类型分组统计
    by_type = {}
    for o in occs:
        t = o["occurrence_type"]
        by_type[t] = by_type.get(t, 0) + 1
    print(f"  类型分布: {by_type}")

    # 展示 definition 类型
    definitions = [o for o in occs if o["occurrence_type"] == "definition"]
    if definitions:
        print(f"\n  Definition ({len(definitions)}条):")
        for d in definitions:
            sentence = d.get("core_sentence", "")
            if sentence:
                display = sentence[:100] + ("..." if len(sentence) > 100 else "")
                print(f"    「{display}」")


def main():
    try:
        login()

        if not check_index_status():
            return

        result = trigger_build()
        # 如果已经 enriched 就跳过等待
        if result.get("message") != "already enriched":
            if not poll_status():
                return

        concepts = check_concepts()
        check_chapter_annotations(concepts)
        check_concept_detail(concepts)

        print("\n" + "=" * 60)
        print("测试完成!")
        print("=" * 60)

    except httpx.HTTPStatusError as e:
        print(f"\nHTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text[:500]}")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
