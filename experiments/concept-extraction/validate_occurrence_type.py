"""
occurrence_type 标注原型验证脚本

用《无条件养育》第一章已提取的 13 个概念，验证 LLM 能否准确区分：
- definition: 作者在定义/解释这个概念
- refinement: 作者在深化、补充、举例说明
- mention: 顺带提及，未展开

使用 Minimax M2.7 (Anthropic API 兼容)
"""

import json
import os
import anthropic

# --- 配置 ---
API_KEY = "sk-cp-io_id9SsGnNlXjOOuMjWdgi4nyNmU6YDNm88NCTOTOpSeVgmDMkSIcsDMtOZ4NxJ6YZhKuLHSuEOJ2NuEi19ELHgaoMDECBIwZroeoOjcDUYLdwnS1jsvcI"
BASE_URL = "https://api.minimaxi.com/anthropic"
MODEL = "MiniMax-M2.7"

# --- 数据路径 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
CONCEPTS_PATH = os.path.join(PROJECT_ROOT, "experiments/parser-prototype/phase1_output_v1.json")
CHAPTER_PATH = os.path.join(PROJECT_ROOT, "experiments/parser-prototype/chapter_dump.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "occurrence_type_output.json")


def load_data():
    """加载概念列表和章节段落"""
    with open(CONCEPTS_PATH, "r", encoding="utf-8") as f:
        concepts = json.load(f)["concepts"]

    with open(CHAPTER_PATH, "r", encoding="utf-8") as f:
        chapter_data = json.load(f)

    # 合并所有章节的段落，附带章节信息
    paragraphs = []
    for chapter in chapter_data["chapters"]:
        for para in chapter["paragraphs"]:
            paragraphs.append({
                "pid": para["pid"],
                "idx": para["idx"],
                "text": para["text"],
                "chapter_idx": chapter["chapter_idx"],
                "chapter_title": chapter["title"],
            })

    return concepts, paragraphs


def build_concept_summary(concepts):
    """构建概念摘要，供 prompt 使用"""
    lines = []
    for c in concepts:
        aliases_str = ", ".join(c["aliases"]) if c["aliases"] else "无"
        lines.append(f'- {c["term"]} (别名: {aliases_str}) [{c["category"]}]')
    return "\n".join(lines)


def build_paragraphs_text(paragraphs):
    """构建段落文本，带编号"""
    lines = []
    for p in paragraphs:
        lines.append(f'[{p["chapter_title"]} | P{p["idx"]:02d} | {p["pid"]}]\n{p["text"]}')
    return "\n\n".join(lines)


SYSTEM_PROMPT = """你是一个精确的文本分析助手，服务于"书的索引库"(Book Language Server)。

你的任务：给定一组已知概念和一批段落，判断每个段落中出现了哪些概念，并标注出现类型。"""


def build_user_prompt(concept_summary, paragraphs_text):
    return f"""## 已知概念列表

{concept_summary}

## 任务

对以下每个段落：
1. 判断该段落是否提到了上述概念列表中的任何概念（通过术语名、别名、或明显的同义表述匹配）
2. 对每次出现，标注类型：
   - `definition`: 作者在此处**定义或解释**这个概念（首次引入、给出含义）
   - `refinement`: 作者在此处**深化、补充、举例说明**这个概念（用例子、研究、对比来展开）
   - `mention`: 顺带提及，未做展开解释

3. 如果该段落没有提到任何已知概念，跳过该段落（不要输出）

## 输出格式

严格 JSON，不要任何解释性前后文：

{{
  "occurrences": [
    {{
      "pid": "段落ID",
      "concept_term": "概念名（用列表中的规范名）",
      "occurrence_type": "definition" | "refinement" | "mention",
      "matched_text": "段落中匹配到概念的原文片段（10-30字）",
      "reasoning": "一句话说明为什么是这个类型"
    }}
  ]
}}

## 重要原则

- 一个段落可以出现多个概念，每个概念单独一条记录
- 同一概念在同一段落只记录一次
- `definition` 应该很少——通常一个概念在全书只有 1-2 处真正在定义
- `refinement` 是作者用例子、研究、对比来丰富概念，比 definition 多但也不泛滥
- `mention` 是最常见的——顺带提了一下，没展开
- matched_text 取原文中最能体现该概念的片段

## 段落文本

{paragraphs_text}

---

现在开始分析。直接输出 JSON，不要任何前后文。"""


def call_llm(system_prompt, user_prompt):
    """调用 Minimax M2.7"""
    client = anthropic.Anthropic(
        api_key=API_KEY,
        base_url=BASE_URL,
    )

    message = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}],
            }
        ],
    )

    # 提取文本响应
    for block in message.content:
        if hasattr(block, "text"):
            return block.text

    return None


def parse_response(response_text):
    """解析 LLM 返回的 JSON"""
    # 尝试直接解析
    text = response_text.strip()

    # 去掉可能的 markdown 代码块包裹
    if text.startswith("```"):
        lines = text.split("\n")
        # 去掉首尾的 ``` 行
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    return json.loads(text)


def analyze_results(occurrences, concepts):
    """分析结果统计"""
    print("\n" + "=" * 60)
    print("结果统计")
    print("=" * 60)

    # 按类型统计
    type_counts = {"definition": 0, "refinement": 0, "mention": 0}
    for occ in occurrences:
        t = occ["occurrence_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    print(f"\n总 occurrences: {len(occurrences)}")
    for t, count in type_counts.items():
        print(f"  {t}: {count}")

    # 按概念统计
    print("\n按概念分布:")
    concept_stats = {}
    for occ in occurrences:
        term = occ["concept_term"]
        if term not in concept_stats:
            concept_stats[term] = {"definition": 0, "refinement": 0, "mention": 0, "total": 0}
        concept_stats[term][occ["occurrence_type"]] += 1
        concept_stats[term]["total"] += 1

    # 按 total 降序
    for term, stats in sorted(concept_stats.items(), key=lambda x: -x[1]["total"]):
        print(f"  {term}: total={stats['total']} "
              f"(def={stats['definition']}, ref={stats['refinement']}, men={stats['mention']})")

    # 未被匹配的概念
    matched_terms = set(concept_stats.keys())
    all_terms = {c["term"] for c in concepts}
    unmatched = all_terms - matched_terms
    if unmatched:
        print(f"\n未匹配到的概念: {unmatched}")

    # 展示所有 definition 类型的（最重要，用于弹窗）
    print("\n" + "-" * 60)
    print("所有 definition 类型（这些将用于悬浮弹窗）:")
    print("-" * 60)
    for occ in occurrences:
        if occ["occurrence_type"] == "definition":
            print(f"\n  概念: {occ['concept_term']}")
            print(f"  段落: {occ['pid']}")
            print(f"  匹配: {occ['matched_text']}")
            print(f"  理由: {occ['reasoning']}")


def main():
    print("加载数据...")
    concepts, paragraphs = load_data()
    print(f"  概念数: {len(concepts)}")
    print(f"  段落数: {len(paragraphs)}")

    concept_summary = build_concept_summary(concepts)
    paragraphs_text = build_paragraphs_text(paragraphs)

    print(f"\n构建 prompt...")
    user_prompt = build_user_prompt(concept_summary, paragraphs_text)
    print(f"  prompt 长度: ~{len(user_prompt)} 字符")

    print(f"\n调用 {MODEL}...")
    response_text = call_llm(SYSTEM_PROMPT, user_prompt)

    if not response_text:
        print("错误: LLM 返回空响应")
        return

    print(f"  响应长度: ~{len(response_text)} 字符")

    print("\n解析响应...")
    try:
        result = parse_response(response_text)
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        print(f"原始响应:\n{response_text[:2000]}")
        # 保存原始响应以便调试
        raw_path = os.path.join(SCRIPT_DIR, "occurrence_type_raw_response.txt")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(response_text)
        print(f"原始响应已保存到: {raw_path}")
        return

    occurrences = result.get("occurrences", [])
    print(f"  解析出 {len(occurrences)} 条 occurrences")

    # 保存结果
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {OUTPUT_PATH}")

    # 分析统计
    analyze_results(occurrences, concepts)


if __name__ == "__main__":
    main()
