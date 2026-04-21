# 概念提取技术方案

> 基于 `concept-extraction-and-hover-design.md` 的实现规划
>
> 日期：2026-04-21

---

## 0. 现状

已实现 LSP v0：
- `IndexedBook` / `IndexedParagraph` 两张表
- `IndexService.build_index()` 解析 EPUB → 段落入库
- 后台任务模式：FastAPI `BackgroundTasks`
- 前端轮询 `/index/status` 等索引完成

本方案在 v0 基础上新增**概念层**，不改动现有表结构。

---

## 1. 整体流程

```
POST /api/books/{book_id}/index          (已有, 不改)
  → EPUB 解析 → indexed_paragraphs 入库
  → status: parsed

POST /api/books/{book_id}/concepts/build (新增)
  → 前置检查: index status == parsed
  → 后台执行 3 个阶段:
      Phase 1: 全书逐章概念扫描 (LLM)
      Phase 2: 跨章去重合并
      Phase 3: 全书段落 occurrence 标注 (LLM)
  → 写入 concepts + concept_occurrences
  → status: enriched
```

---

## 2. 数据库

### 2.1 新增表: `concepts`

```python
class Concept(Base):
    __tablename__ = "concepts"

    id          = Column(String, primary_key=True)       # concept:{uuid4}
    book_id     = Column(String, ForeignKey("books.id"), nullable=False)
    user_id     = Column(String, ForeignKey("users.id"), nullable=False)

    term        = Column(String, nullable=False)          # 规范名
    aliases     = Column(JSON, nullable=False, default=[]) # 别名列表
    category    = Column(String, nullable=False)          # term/term_custom/person/work/theory

    # 频次统计 (Phase 3 之后回填)
    total_occurrences = Column(Integer, default=0)
    chapter_count     = Column(Integer, default=0)        # 出现在几个章节
    scope             = Column(String, default="chapter") # book / chapter

    created_at  = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_concepts_user_book", "user_id", "book_id"),
    )
```

### 2.2 新增表: `concept_occurrences`

```python
class ConceptOccurrence(Base):
    __tablename__ = "concept_occurrences"

    id               = Column(String, primary_key=True)    # occ:{uuid4}
    concept_id       = Column(String, ForeignKey("concepts.id"), nullable=False)
    paragraph_id     = Column(String, ForeignKey("indexed_paragraphs.id"), nullable=False)
    user_id          = Column(String, nullable=False)
    book_id          = Column(String, nullable=False)
    chapter_idx      = Column(Integer, nullable=False)

    occurrence_type  = Column(String, nullable=False)      # definition/refinement/mention
    matched_text     = Column(Text, nullable=True)         # 匹配的原文片段
    core_sentence    = Column(Text, nullable=True)         # 弹窗展示用核心句
    reasoning        = Column(Text, nullable=True)         # LLM 标注理由

    created_at       = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_occ_user_book", "user_id", "book_id"),
        Index("idx_occ_concept", "concept_id"),
        Index("idx_occ_paragraph", "paragraph_id"),
        Index("idx_occ_user_book_chapter", "user_id", "book_id", "chapter_idx"),
    )
```

### 2.3 IndexedBook 扩展字段

```python
# 在 indexed_books 表新增:
concept_status = Column(String, default=None)  # None/extracting/enriched/failed
concept_error  = Column(Text, nullable=True)
total_concepts = Column(Integer, default=0)
```

### 2.4 Migration

新建 `016_add_concept_tables.py`，创建上述两张表 + alter indexed_books。

---

## 3. 后端 Service

### 3.1 新建 `ConceptService`

文件：`app/services/concept_service.py`

```python
class ConceptService:

    # --- LLM 配置 ---
    CLIENT = anthropic.Anthropic(
        api_key=settings.minimax_api_key,
        base_url=settings.minimax_base_url,
    )
    MODEL = "MiniMax-M2.7"

    # --- Build ---

    @classmethod
    def build_concepts(cls, book_id: str, user_id: str, rebuild: bool = False):
        """全流程: Phase 1 → 2 → 3"""
        cls._set_status(book_id, user_id, "extracting")
        try:
            # Phase 1: 全书逐章概念扫描
            raw_concepts = cls._phase1_extract(book_id, user_id)

            # Phase 2: 跨章去重合并
            concepts = cls._phase2_deduplicate(raw_concepts)
            cls._save_concepts(book_id, user_id, concepts)

            # Phase 3: 全书段落 occurrence 标注
            occurrences = cls._phase3_annotate(book_id, user_id, concepts)
            cls._save_occurrences(book_id, user_id, occurrences)

            # 回填频次统计
            cls._update_stats(book_id, user_id)

            cls._set_status(book_id, user_id, "enriched")
        except Exception as e:
            cls._set_status(book_id, user_id, "failed", str(e))
            raise

    # --- Phase 1: 逐章概念扫描 ---

    @classmethod
    def _phase1_extract(cls, book_id: str, user_id: str) -> list[dict]:
        """
        对每一章调用 LLM 提取概念。

        输入:
          - 本章所有段落 (从 indexed_paragraphs 查)
          - 全书目录 (所有章节标题, 提供全书语境)

        输出:
          - 每章的概念列表, 带 chapter_idx 来源标记
        """
        chapters = IndexService.get_chapters(book_id, user_id)
        toc = cls._build_toc(chapters)  # 全书目录字符串

        all_concepts = []
        for chapter in chapters:
            paragraphs = IndexService.get_paragraphs(
                book_id, user_id, chapter_idx=chapter["chapter_idx"]
            )
            if not paragraphs:
                continue

            result = cls._call_phase1_llm(toc, chapter, paragraphs)
            for concept in result:
                concept["source_chapter_idx"] = chapter["chapter_idx"]
            all_concepts.extend(result)

        return all_concepts

    @classmethod
    def _call_phase1_llm(cls, toc: str, chapter: dict, paragraphs: list) -> list:
        """
        调用 LLM 提取单章概念。
        Prompt 核心: prompt_phase1.md + 附带全书目录。
        """
        paragraphs_text = "\n\n".join(
            f'[P{p["para_idx"]:02d}|{p["pid"]}]\n{p["text"]}'
            for p in paragraphs
        )

        prompt = f"""你是一个精确的学术术语抽取助手, 服务于"书的索引库"(Book Language Server).

## 全书目录 (供判断概念全书重要性)

{toc}

## 当前章节: {chapter["chapter_title"]}

## 什么是"核心概念"

必须抽取:
1. 作者特意定义、反复使用、有专门含义的术语 (包括作者自创的)
2. 被作者引用其观点/研究/理论的人名
3. 被引用的作品: 书籍、论文、理论流派

不要抽取:
1. 常识词 / 过于泛泛的词
2. 例子里偶然出现的人名
3. 普通描述中出现的物品/动作

## 分类: term / term_custom / person / work / theory

## 输出: 严格 JSON

{{
  "concepts": [
    {{
      "term": "规范名",
      "aliases": ["别名1"],
      "category": "term",
      "reasoning": "一句话说明"
    }}
  ]
}}

aliases 只收录原文出现过的变体, 不要自行翻译。
宁少勿多, 每 10 段 ≤ 5 个。

## 章节文本

{paragraphs_text}

---

直接输出 JSON。"""

        message = cls.CLIENT.messages.create(
            model=cls.MODEL,
            max_tokens=4000,
            system="你是一个精确的学术术语抽取助手。",
            messages=[{"role": "user", "content": prompt}],
        )
        return cls._parse_json_response(message)["concepts"]

    # --- Phase 2: 跨章去重 ---

    @classmethod
    def _phase2_deduplicate(cls, raw_concepts: list[dict]) -> list[dict]:
        """
        合并策略:
          1. 完全同名 → 合并, aliases 取并集
          2. 别名匹配 → A 的 term 出现在 B 的 aliases 中 → 合并
          3. (可选) embedding 相似度 > 阈值 → 合并

        当前 v1 只做 1 + 2 (纯文本匹配), 不上 embedding。
        """
        merged = {}  # normalized_term → concept dict
        alias_map = {}  # alias → normalized_term

        for c in raw_concepts:
            term = c["term"].strip()
            term_lower = term.lower()

            # 检查是否已存在 (term 或 alias 匹配)
            existing_key = None
            if term_lower in merged:
                existing_key = term_lower
            elif term_lower in alias_map:
                existing_key = alias_map[term_lower]
            else:
                for alias in c.get("aliases", []):
                    alias_lower = alias.strip().lower()
                    if alias_lower in merged:
                        existing_key = alias_lower
                        break
                    if alias_lower in alias_map:
                        existing_key = alias_map[alias_lower]
                        break

            if existing_key:
                # 合并 aliases
                existing = merged[existing_key]
                new_aliases = set(existing.get("aliases", []))
                new_aliases.update(c.get("aliases", []))
                new_aliases.discard(existing["term"])
                existing["aliases"] = list(new_aliases)
                # 记录来源章节
                existing.setdefault("source_chapters", [])
                if c.get("source_chapter_idx") not in existing["source_chapters"]:
                    existing["source_chapters"].append(c["source_chapter_idx"])
            else:
                # 新概念
                merged[term_lower] = {
                    "term": term,
                    "aliases": c.get("aliases", []),
                    "category": c.get("category", "term"),
                    "reasoning": c.get("reasoning", ""),
                    "source_chapters": [c.get("source_chapter_idx")],
                }
                # 注册 aliases
                for alias in c.get("aliases", []):
                    alias_map[alias.strip().lower()] = term_lower

        return list(merged.values())

    # --- Phase 3: 全书段落标注 ---

    @classmethod
    def _phase3_annotate(
        cls, book_id: str, user_id: str, concepts: list[dict]
    ) -> list[dict]:
        """
        拿合并后的概念列表, 逐章扫描全书段落, 标注 occurrence_type。

        按章调用 LLM, 每次传入:
          - 完整概念列表 (所有概念的 term + aliases)
          - 本章所有段落
        """
        chapters = IndexService.get_chapters(book_id, user_id)
        concept_summary = cls._build_concept_summary(concepts)

        all_occurrences = []
        for chapter in chapters:
            paragraphs = IndexService.get_paragraphs(
                book_id, user_id, chapter_idx=chapter["chapter_idx"]
            )
            if not paragraphs:
                continue

            result = cls._call_phase3_llm(
                concept_summary, chapter, paragraphs
            )
            for occ in result:
                occ["chapter_idx"] = chapter["chapter_idx"]
            all_occurrences.extend(result)

        return all_occurrences

    @classmethod
    def _call_phase3_llm(
        cls, concept_summary: str, chapter: dict, paragraphs: list
    ) -> list:
        """
        调用 LLM 标注单章段落中的概念出现。
        复用验证脚本中已验证的 prompt 结构。
        """
        paragraphs_text = "\n\n".join(
            f'[P{p["para_idx"]:02d}|{p["pid"]}]\n{p["text"]}'
            for p in paragraphs
        )

        prompt = f"""## 已知概念列表

{concept_summary}

## 当前章节: {chapter["chapter_title"]}

## 任务

对以下每个段落:
1. 判断该段落是否提到了上述概念（通过术语名、别名、或同义表述）
2. 对每次出现，标注类型:
   - `definition`: 作者在此处定义或解释这个概念
   - `refinement`: 作者在此处深化、补充、举例说明
   - `mention`: 顺带提及，未展开
3. 提取 core_sentence: 如果是 definition 或 refinement, 提取作者原文中最核心的 1-2 句话（用于弹窗展示, 控制在 100 字内）
4. 没提到任何概念的段落跳过

## 输出: 严格 JSON

{{
  "occurrences": [
    {{
      "pid": "段落ID (用 [P##|pid] 中的 pid)",
      "concept_term": "概念规范名",
      "occurrence_type": "definition|refinement|mention",
      "matched_text": "段落中匹配到概念的原文片段 (10-30字)",
      "core_sentence": "作者解释该概念的核心句 (仅 definition/refinement, 100字内)",
      "reasoning": "一句话说明为什么是这个类型"
    }}
  ]
}}

## 重要原则

- 一个段落可出现多个概念, 每个单独一条
- definition 应很少——通常一个概念全书只有 1-2 处真正在定义
- refinement 比 definition 多但也不泛滥
- mention 最常见
- core_sentence 只在 definition 和 refinement 时提供, mention 留空

## 段落文本

{paragraphs_text}

---

直接输出 JSON。"""

        message = cls.CLIENT.messages.create(
            model=cls.MODEL,
            max_tokens=8000,
            system="你是一个精确的文本分析助手，服务于书的索引库。",
            messages=[{"role": "user", "content": prompt}],
        )
        return cls._parse_json_response(message)["occurrences"]

    # --- 存储 ---

    @classmethod
    def _save_concepts(cls, book_id, user_id, concepts):
        """写入 concepts 表"""
        with get_db() as db:
            # 先清旧数据
            db.query(Concept).filter_by(book_id=book_id, user_id=user_id).delete()
            for c in concepts:
                db.add(Concept(
                    id=f"concept:{uuid4()}",
                    book_id=book_id,
                    user_id=user_id,
                    term=c["term"],
                    aliases=c["aliases"],
                    category=c["category"],
                ))
            db.commit()

    @classmethod
    def _save_occurrences(cls, book_id, user_id, occurrences):
        """写入 concept_occurrences 表"""
        with get_db() as db:
            # 先清旧数据
            db.query(ConceptOccurrence).filter_by(
                book_id=book_id, user_id=user_id
            ).delete()

            # 建 term → concept_id 映射
            concepts = db.query(Concept).filter_by(
                book_id=book_id, user_id=user_id
            ).all()
            term_to_id = {c.term: c.id for c in concepts}

            for occ in occurrences:
                concept_id = term_to_id.get(occ["concept_term"])
                if not concept_id:
                    continue
                db.add(ConceptOccurrence(
                    id=f"occ:{uuid4()}",
                    concept_id=concept_id,
                    paragraph_id=occ["pid"],
                    user_id=user_id,
                    book_id=book_id,
                    chapter_idx=occ["chapter_idx"],
                    occurrence_type=occ["occurrence_type"],
                    matched_text=occ.get("matched_text"),
                    core_sentence=occ.get("core_sentence"),
                    reasoning=occ.get("reasoning"),
                ))
            db.commit()

    @classmethod
    def _update_stats(cls, book_id, user_id):
        """回填 concepts 表的频次统计 + indexed_books 的概念计数"""
        with get_db() as db:
            concepts = db.query(Concept).filter_by(
                book_id=book_id, user_id=user_id
            ).all()

            total_chapters = db.query(IndexedBook).filter_by(
                book_id=book_id, user_id=user_id
            ).first().total_chapters

            for c in concepts:
                occs = db.query(ConceptOccurrence).filter_by(
                    concept_id=c.id
                ).all()
                c.total_occurrences = len(occs)
                c.chapter_count = len(set(o.chapter_idx for o in occs))
                # 出现在 ≥50% 章节 → book 级
                c.scope = "book" if c.chapter_count >= total_chapters * 0.5 else "chapter"

            # 更新 indexed_books
            record = db.query(IndexedBook).filter_by(
                book_id=book_id, user_id=user_id
            ).first()
            record.total_concepts = len(concepts)

            db.commit()

    # --- 工具方法 ---

    @classmethod
    def _build_toc(cls, chapters):
        return "\n".join(
            f'{ch["chapter_idx"]}. {ch["chapter_title"]} ({ch["paragraph_count"]}段)'
            for ch in chapters
        )

    @classmethod
    def _build_concept_summary(cls, concepts):
        lines = []
        for c in concepts:
            aliases = ", ".join(c["aliases"]) if c["aliases"] else "无"
            lines.append(f'- {c["term"]} (别名: {aliases}) [{c["category"]}]')
        return "\n".join(lines)

    @classmethod
    def _parse_json_response(cls, message):
        text = ""
        for block in message.content:
            if hasattr(block, "text"):
                text = block.text
                break
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)
```

### 3.2 配置扩展

`shared/config.py` 新增：

```python
# Minimax LLM
minimax_api_key: str = ""
minimax_base_url: str = "https://api.minimaxi.com/anthropic"
minimax_model: str = "MiniMax-M2.7"
```

`.env` 新增：

```
MINIMAX_API_KEY=sk-cp-...
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
```

---

## 4. API 端点

### 4.1 新建 `app/routers/concepts.py`

```
POST   /api/books/{book_id}/concepts/build          触发概念提取 (异步后台)
GET    /api/books/{book_id}/concepts/status          概念提取状态
GET    /api/books/{book_id}/concepts                 获取概念列表
GET    /api/books/{book_id}/concepts/{concept_id}    单个概念详情 + occurrences
GET    /api/books/{book_id}/concepts/by-chapter/{chapter_idx}
                                                     某章的概念角标数据
DELETE /api/books/{book_id}/concepts                 删除概念数据
```

### 4.2 关键端点详解

#### `GET /concepts/by-chapter/{chapter_idx}`

**这是前端渲染角标的核心接口**。返回该章需要展示的概念角标：

```json
{
  "book_id": "xxx",
  "chapter_idx": 5,
  "annotations": [
    {
      "concept_id": "concept:uuid",
      "term": "有条件养育",
      "badge_number": 1,
      "first_pid_in_chapter": "sig:xxx:yyy:zzz-003",
      "popover": {
        "term": "有条件养育",
        "explanations": [
          {
            "core_sentence": "家长对孩子的爱出于'他们做了什么'——孩子只有在做到家长期望或达到所规定的标准之后才可以得到",
            "source": "第一章 第3段",
            "chapter_idx": 5,
            "pid": "sig:xxx:yyy:zzz-003"
          }
        ]
      }
    }
  ]
}
```

**逻辑**：
1. 查该章所有 occurrences (type = definition 或 refinement)
2. 按 concept 分组, 每个 concept 取首次出现位置
3. 弹窗内容: 只取 `chapter_idx <= 当前章` 的 definition/refinement, 按章节顺序排列, 最多 2 条
4. badge_number 按概念在本章首次出现的段落顺序编号
5. 只返回该章重点概念 (scope=book, 或在本章有 definition/refinement 的)

#### `GET /concepts/{concept_id}`

返回单个概念的完整信息, 包含所有 occurrences：

```json
{
  "concept_id": "concept:uuid",
  "term": "有条件养育",
  "aliases": ["有条件的爱"],
  "category": "term_custom",
  "total_occurrences": 18,
  "chapter_count": 8,
  "scope": "book",
  "occurrences": [
    {
      "pid": "sig:xxx",
      "chapter_idx": 5,
      "chapter_title": "第一章 有条件养育",
      "occurrence_type": "definition",
      "matched_text": "前者是有条件的爱...",
      "core_sentence": "..."
    }
  ]
}
```

---

## 5. 文件清单

```
epub-tts-backend/
├── alembic/versions/
│   └── 016_add_concept_tables.py        # migration
├── shared/models/
│   └── concept.py                       # Concept, ConceptOccurrence ORM
├── app/services/
│   └── concept_service.py               # ConceptService (Phase 1-3)
├── app/routers/
│   └── concepts.py                      # REST API
└── shared/config.py                     # +minimax 配置
```

---

## 6. 执行计划

### Step 1: 基础设施
- [ ] 新增 ORM models (`shared/models/concept.py`)
- [ ] 新增 migration (`016_add_concept_tables.py`)
- [ ] config 新增 minimax 配置
- [ ] `.env` 加入 API key

### Step 2: ConceptService 核心逻辑
- [ ] Phase 1: `_phase1_extract` + `_call_phase1_llm`
- [ ] Phase 2: `_phase2_deduplicate`
- [ ] Phase 3: `_phase3_annotate` + `_call_phase3_llm`
- [ ] 存储: `_save_concepts`, `_save_occurrences`, `_update_stats`

### Step 3: API 端点
- [ ] `concepts.py` router, 注册到 `main.py`
- [ ] `POST /concepts/build` + 后台任务
- [ ] `GET /concepts/status`
- [ ] `GET /concepts` (列表)
- [ ] `GET /concepts/by-chapter/{chapter_idx}` (角标数据)

### Step 4: 端到端验证
- [ ] 用《无条件养育》跑全流程
- [ ] 检查 definition 标注质量 (弹窗内容是否是作者原文解释)
- [ ] 检查角标数据是否正确

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Phase 3 LLM 输出 JSON 格式错误 | 个别章节标注失败 | 加 retry + 宽松 JSON 解析 |
| 概念过多导致 prompt 超长 | 某章标注不完整 | 按概念数拆分多次调用 |
| definition/mention 分错 | 弹窗展示无意义内容 | core_sentence 只在 def/ref 时生成, mention 不影响弹窗 |
| LLM 返回的 pid 不在 DB 中 | occurrence 存储失败 | pid 校验, 不匹配的跳过并 log |
| 全书概念扫描耗时较长 | 用户等待体验差 | 后台任务 + 进度轮询 (可在 indexed_books 记录当前 phase) |

---

## 8. 成本估算

以 10 章 500 段的书为例 (Minimax M2.7):

| 阶段 | LLM 调用次数 | 输入 tokens | 输出 tokens |
|------|-------------|------------|------------|
| Phase 1 (概念扫描) | 10 次 | ~120K | ~20K |
| Phase 2 (去重) | 0 (纯算法) | 0 | 0 |
| Phase 3 (标注) | 10 次 | ~150K | ~50K |
| **合计** | **20 次** | **~270K** | **~70K** |

Minimax 价格远低于 Anthropic, 全书提取成本在几毛钱级别。
