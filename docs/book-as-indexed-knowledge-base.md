# BookReader: Book as Indexed Knowledge Base

> **核心理念**：把每一本书，从一堆可阅读的字符串，变成一个可查询的知识库。
>
> **产品定位**：**The LSP for Books** — 索引化的书，不是数字化的书、不是聊天化的书。
>
> 本文档是 BookReader 的架构宪法。所有后续功能设计都应在此框架下展开。

---

## 0. TL;DR

1. 过去几千年，书一直是"可阅读但不可查询"的文本。
2. 代码几十年前也是同样处境，靠 Language Server Protocol (LSP) 演化成了可查询的对象。
3. LLM 让"给一本书做语义索引"第一次在工程上可行。
4. BookReader 的底层不是"AI 阅读助手"，是 **Book Language Server**。
5. 所有上层功能（翻译、术语解释、原话溯源、跨书聚合、学习 Agent、GEO）都是 Index 上的**不同查询**。
6. **先把 Index 做扎实，Agent 自然生长**。没有 Index，所有 Agent 都是在碎片上瞎猜。

---

## 1. LSP 简史

### 1.1 LSP 之前：N × M 的噩梦

过去每个编辑器要支持每门语言，都要独立实现：

```
VS Code × Python 支持
VS Code × Go 支持
Vim × Python 支持
Vim × Go 支持
Emacs × Python 支持
...

N 个编辑器 × M 门语言 = N × M 次重复工作
```

### 1.2 LSP 的核心思想：解耦

微软 2016 年提出 LSP：

```
┌─────────────────┐           ┌────────────────────────┐
│ Language Client │  ◀─────▶  │ Language Server        │
│ (编辑器)         │   协议    │ (懂这门语言的程序)       │
└─────────────────┘           └────────────────────────┘
```

- 编辑器只需要"说 LSP"
- 语言服务只需要懂这门语言
- 两边通过协议通信，互不关心对方实现
- 复杂度从 N × M 降到 N + M

### 1.3 协议规定了一套语义查询

约 30+ 个标准操作：

```
textDocument/definition       跳转定义
textDocument/references       查找所有引用
textDocument/hover            悬停信息
textDocument/completion       自动补全
textDocument/rename           重命名符号
textDocument/codeAction       快速修复
workspace/symbol              跨文件搜索符号
workspace/executeCommand      执行命令
...
```

每个查询都有**结构化的输入输出**（JSON-RPC）。

### 1.4 LSP 能用在代码之外吗

**能**。协议本身是通用的。已经有人做：

- **LTeX** — 自然语言的语法检查
- **Marksman** — Markdown 笔记（跳转引用、查反链）
- **Texlab** — LaTeX 交叉引用
- **YAML Language Server** — 配置 schema 校验

**LSP 适用的前提**：
1. 内容是**结构化**的
2. 里面有可命名的**实体**
3. 实体间有**关系**
4. 用户需要**语义查询**

**书完美符合这四个条件。但数千年来没人做过。**

---

## 2. 为什么 grep 远远不够

### 2.1 grep 是字面的，不是语义的

用户想查"ATR"这个概念在书中的所有出现：

```
grep 能找到:
  ✓ "ATR is an indicator..."
  ✓ "calculate the ATR as..."

grep 找不到:
  ✗ "Wilder's original measure..."   (作者换说法)
  ✗ "the average true range..."       (全称)
  ✗ "this volatility metric..."       (代词指代)
  ✗ "前文提到的那个波动指标..."         (中文指代)
```

### 2.2 grep 不懂结构

grep 只告诉你"ATR"在哪一行，不告诉你：
- 哪一处是**定义**
- 哪一处是**使用**
- 哪一处是**补充说明**
- 这三者应该分别看

### 2.3 grep 不能跨语言

```
一本英文书里 "emergence"
一本中文书里 "涌现"
grep 认为它们无关, 实际是同一概念
```

### 2.4 代码世界早就学过这一课

```
1990s:  grep + ctags 找代码引用   —— 能用, 精度差
2000s:  IDE 内置语法分析          —— 好用, 但每个 IDE 重复造轮子
2016+:  LSP                     —— 解耦, 标准化, 索引化时代

书的当下处境, 相当于 1990s 的代码.
```

**而且书比代码更需要语义索引**：代码语法精确，grep 失真小；书语义模糊，grep 失真大。

---

## 3. 核心理念：Book as Indexed Knowledge Base

### 3.1 书有天然的结构

```
Book
 ├── Chapter
 │    ├── Section
 │    │    ├── Paragraph
 │    │    │    └── Sentence
 │    │    └── ...
 │    └── ...
 └── Metadata (author, ISBN, language, ...)
```

EPUB 格式天然暴露这个结构，解析成本低。

### 3.2 书有语义实体（Symbols）

```
Concept        概念/术语       ("ATR", "涌现", "反脆弱")
Person         人名           ("Kahneman", "Wilder")
Work           引用的其他书/论文 ("Wilder 1978", "Thinking Fast and Slow")
Example        具体例子/案例    ("IBM 2003 年的股价...")
Claim          关键论断        ("损失厌恶是收益的 2 倍")
Formula        公式/算法       ("ATR = max(|H-L|, ...)")
Figure         图表            ("Figure 3.2")
```

### 3.3 书有语义关系（Relations）

```
Defines         作者在定义一个概念
Uses            作者在使用一个已定义概念
Refines         作者补充/深化了一个概念
Contrasts       作者对比了两个概念
DependsOn       "理解 B 需要先懂 A"
References      引用了外部著作
Exemplifies     用某例子说明某概念
Contradicts     作者挑战了某观点（自己前面的 or 别人的）
```

### 3.4 书可以被语义查询

```
"ATR 在哪定义的?"               → 跳到定义
"ATR 所有出现在哪?"              → 全部引用
"这本书的概念大纲?"              → Outline
"这段用到了哪些之前定义的概念?"    → Breadcrumbs
"该概念在作者其他书里出现过吗?"    → Workspace Symbol
"有没有和它相关的概念?"          → Type Hierarchy
"作者哪里自相矛盾了?"            → Diagnostics
```

**这些全部对应 LSP 的标准查询**。

---

## 4. Book LSP 完整映射

```
═══════════════════════════════════════════════════════════════
  代码世界                      书的世界
═══════════════════════════════════════════════════════════════

─── Symbols ───
 Class / Function / Type   →   Concept / 术语
 Variable                  →   具体实例 / 人名
 Import                    →   引用的其他书 / 论文
 Test case                 →   作者举的例子
 Assertion / Invariant     →   关键论断

─── Relations ───
 Definition                →   📌 首次定义处
 Reference                 →   🎯 所有使用处
 Override / Refinement     →   💡 补充、深化
 Overload                  →   同一术语在不同语境的用法
 Inheritance               →   概念的上下位关系
 Dependency                →   "理解 B 需先懂 A"
 Comment                   →   用户批注

─── Queries ───
 Go to Definition          →   跳转首次定义
 Find All References       →   所有出现 (分类: 定义/补充/使用)
 Peek Definition           →   悬浮预览, 不离开当前位置
 Hover                     →   悬停看简短定义
 Symbol Search             →   模糊搜索概念
 Workspace Symbols         →   跨书搜索
 Rename Symbol             →   全书术语校正
 Call Hierarchy            →   "谁用了这个 / 这个用了谁"
 Type Hierarchy            →   概念的上下位图谱
 Code Action               →   "补全这段的理解" / "生成复习卡片"

─── Views ───
 Outline                   →   全书概念大纲
 Breadcrumbs               →   本段用到的已定义概念
 Minimap                   →   某概念在全书的分布热力图
 Problems Panel            →   作者自相矛盾/定义不清的地方

─── Engineering ───
 Project / Workspace       →   一本书 / 用户的书架
 .cache / index file       →   .bookindex  (扫描一次, 终身复用)
 Incremental compilation   →   用户改译 → 局部重建索引
 LSP protocol              →   Book Language Server Protocol
 Language Server           →   Book Language Server

─── 跨书 / 跨语言 ───
 Monorepo                  →   用户的整个书架
 Linked projects           →   跨书术语聚合
 Symbol resolution         →   指代消歧 (作者说"前文所讲" 指哪个)
```

---

## 5. 架构：四层模型

```
┌──────────────────────────────────────────────────┐
│ Application Layer                                │
│  阅读器 / 搜索 / 讨论 Agent / 学习 Agent / GEO   │
├──────────────────────────────────────────────────┤
│ Query Layer  (Book LSP API)                     │
│  goToDefinition / findReferences / hover / ...   │
├──────────────────────────────────────────────────┤
│ Index Layer  ← 核心竞争力                         │
│  Concepts / Relations / Occurrences / Versions   │
├──────────────────────────────────────────────────┤
│ Parser & Extractor                              │
│  EPUB → AST + LLM 语义抽取                       │
├──────────────────────────────────────────────────┤
│ Raw Content                                     │
│  EPUB / PDF / Plain text                         │
└──────────────────────────────────────────────────┘
```

### 5.1 Raw Content 层

- 原始电子书文件（EPUB / PDF / TXT）
- 用户上传或系统内建
- 不做修改，持久保留

### 5.2 Parser & Extractor 层

两步处理：

**语法 Parse**（零 LLM 成本）：
- EPUB → 章节 → 段落 → 句子 AST
- 提取元数据、章节锚点
- 建立段落稳定 ID（用于跳转与批注锚点）

**语义 Extract**（LLM 扫描，一次成本）：
- 识别概念/术语/人名
- 标注每次出现的类型（define / refine / use）
- 识别概念间关系
- 输出置信度标签

关键设计：**扫描结果是结构化 JSON，不是自由文本**。

### 5.3 Index Layer

这是 BookReader 的核心资产。数据组织为：

- **Concepts**：所有被识别的概念（书内 + 跨书）
- **Occurrences**：每次出现的位置、类型、上下文
- **Relations**：概念间的关系图
- **Versions**：用户修订、反馈、批注（索引随使用进化）

### 5.4 Query Layer

提供一套标准化的查询 API（详见第 7 节）。

所有应用层功能**只能通过 Query Layer 访问 Index**，保证：
- 应用层功能易替换、易扩展
- Index 变化不破坏上层
- 未来可开放协议给第三方

### 5.5 Application Layer

所有用户可见的功能：
- 阅读器（带术语高亮、悬停、跳转）
- 翻译（按章节，术语一致）
- 术语解释（借 Index 的 Occurrences）
- 原话溯源（借 Index 的 References）
- 跨书聚合（借 Index 的 Workspace）
- 学习 Agent（基于 Index 生成问题）
- GEO 页面（基于 Index 的聚合）

---

## 6. Index Schema（初版）

```sql
-- 书
CREATE TABLE books (
  id            TEXT PRIMARY KEY,
  title         TEXT,
  author        TEXT,
  language      TEXT,
  isbn          TEXT,
  epub_hash     TEXT,        -- 同书不同版本区分
  indexed_at    TIMESTAMP,
  index_version TEXT         -- 索引 schema 版本
);

-- 结构化段落 (跳转和锚点基础)
CREATE TABLE paragraphs (
  id            TEXT PRIMARY KEY,     -- 稳定 ID, 不随排版变
  book_id       TEXT,
  chapter_idx   INT,
  chapter_name  TEXT,
  position      INT,                  -- 章内顺序
  text          TEXT
);

-- 概念 (Symbol)
CREATE TABLE concepts (
  id                TEXT PRIMARY KEY,
  canonical_name    TEXT,              -- 规范名
  aliases           TEXT[],            -- 别名 ("ATR" / "Average True Range")
  category          TEXT,              -- term / person / work / formula / ...
  book_id           TEXT,              -- 首次定义所在书 (跨书时可为 null)
  first_occurrence  TEXT,              -- paragraph_id
  short_definition  TEXT,              -- 黄金摘录, 用于浮层预览
  user_notes        TEXT,              -- 用户手动注释
  confidence        REAL               -- 0-1, LLM 识别置信度
);

-- 每次出现
CREATE TABLE occurrences (
  id               TEXT PRIMARY KEY,
  concept_id       TEXT,
  paragraph_id     TEXT,
  book_id          TEXT,
  occurrence_type  TEXT,   -- 'definition' | 'refinement' | 'usage' | 'contrast'
  is_first_def     BOOL,
  context_before   TEXT,   -- 前 1 句
  context_after    TEXT,   -- 后 1 句
  extracted_note   TEXT,   -- LLM 对这次出现的提取 (可选)
  confidence       REAL
);

-- 概念间关系 (图)
CREATE TABLE relations (
  id              TEXT PRIMARY KEY,
  from_concept    TEXT,
  to_concept      TEXT,
  relation_type   TEXT,   -- 'refines' | 'contrasts' | 'depends_on' | 'is_a' | ...
  evidence_occur  TEXT,   -- 哪次 occurrence 支持这个关系
  confidence      REAL
);

-- 跨书聚合 (用户主导)
CREATE TABLE concept_merges (
  id            TEXT PRIMARY KEY,
  canonical_id  TEXT,           -- 合并后的 concept id
  merged_ids    TEXT[],         -- 被合并的 concept ids
  merged_by     TEXT,           -- 'user' | 'auto_literal' | 'auto_semantic'
  merged_at     TIMESTAMP,
  reversible    BOOL            -- 允许撤销
);

-- 用户版本 (索引随使用进化)
CREATE TABLE user_revisions (
  id            TEXT PRIMARY KEY,
  user_id       TEXT,
  target_type   TEXT,           -- 'concept' | 'occurrence' | 'relation'
  target_id     TEXT,
  action        TEXT,           -- 'correct' | 'add' | 'delete' | 'rename'
  payload       JSONB,
  created_at    TIMESTAMP
);

-- 翻译缓存 (挂在 paragraph 上)
CREATE TABLE translations (
  paragraph_id  TEXT,
  target_lang   TEXT,
  text          TEXT,
  term_spans    JSONB,           -- 术语位置标记 (用于前端高亮)
  model         TEXT,
  created_at    TIMESTAMP,
  PRIMARY KEY (paragraph_id, target_lang)
);
```

**几个设计要点**：

1. **Paragraph ID 稳定化**：不依赖行号/偏移，用内容 hash + 位置签名，让跳转锚点持久有效。详细算法见 `paragraph-id-design.md`。
2. **Confidence 字段无处不在**：所有 LLM 产出的结构都带置信度，驱动 UI 的可信度标注。
3. **用户修订独立表**：索引可修正，且可审计——你改过什么、何时改的都留痕。
4. **Merges 可逆**：跨书聚合的误判必须可撤销。
5. **Aliases 原生支持**：同一概念的不同说法（"ATR" / "Average True Range"）在一个 concept 下。

### 6.1 存储选型

**结论：SQLite (MVP) → PostgreSQL + pgvector（需要向量搜索时）。不用 MongoDB。**

判断依据：

```
数据本质: 强关系 (concepts ↔ occurrences ↔ paragraphs ↔ books)
查询模式: 大量 JOIN + 全文搜索 + 图遍历 + 聚合
JSON 字段: 少量 (term_spans, payload, aliases), JSONB 完全够用
未来诉求: 向量搜索 (pgvector 成熟) + 可能的图查询

→ 这是"有少量 JSON 字段的关系数据", 不是"JSON 文档"
→ MongoDB 的 schema-less 优势此处是负债 (schema 会变, 区别只是"强制迁移"还是"代码堵漏")
```

**MongoDB 在此不适用的具体原因**：
- JOIN 用 aggregate pipeline 又慢又绕
- 全文搜索能力弱于 FTS5 / tsvector
- 无外键, 引用完整性无法保证
- 向量搜索生态弱于 pgvector

**per-book 组织**（推荐）：

```
~/.bookreader/
├── global.db                        书架元信息 + 跨书概念映射
└── books/
    ├── elder-trading.bookindex       SQLite, 一本书一个文件
    ├── kahneman-fast.bookindex
    └── ...
```

**优点**：每本书的 Index 是可独立迁移/分享/归档的资产，契合 §10 原则 6（"索引是用户资产"）。跨书查询用 SQLite `ATTACH DATABASE`。

**迁移路径**：

```
SQLite (self-use, MVP/v1)
  ↓  需要向量搜索 / 跨书规模变大
PostgreSQL + pgvector
  ↓  用户量大 (大概率用不到)
分库 / 专用 graph DB
```

schema 差异极小，迁移风险低。

**代码世界的前例佐证**：rust-analyzer、clangd、pyright、Sourcegraph 都用嵌入式/关系存储，无人用 MongoDB 存 LSP 索引。Book LSP 同构。

---

## 7. Query API（初版）

类比 LSP 的标准查询，Book LSP 提供如下接口：

```typescript
// ─── 基础查询 ───

/** 跳到概念的首次定义 */
goToDefinition(conceptId): Location

/** 所有出现位置, 可按类型过滤 */
findReferences(
  conceptId,
  opts?: { types?: ('definition'|'refinement'|'usage')[] }
): Occurrence[]

/** 悬停预览 (简短定义 + 统计) */
hover(conceptId): {
  shortDef: string,
  firstDefLocation: Location,
  occurrenceCount: { definition, refinement, usage },
  relatedConcepts: Concept[]
}

/** 搜索概念 (支持别名、模糊) */
searchSymbols(query: string, scope: 'book'|'workspace'): Concept[]

// ─── 结构查询 ───

/** 本段用到了哪些已定义概念 (breadcrumbs) */
documentSymbols(paragraphId): Concept[]

/** 全书大纲 */
outline(bookId): ConceptTree

/** 概念在全书的分布 (用于 minimap) */
distributionMap(conceptId): ParagraphId[]

// ─── 图查询 ───

/** 上下位/相关概念 */
typeHierarchy(conceptId): ConceptGraph

/** 该概念使用了哪些前置概念, 又被哪些后续概念使用 */
callHierarchy(conceptId): {
  uses: Concept[],       // 前置
  usedBy: Concept[]      // 后续
}

// ─── 跨书 ───

/** 跨书搜索 */
workspaceSymbols(query: string): Concept[]

/** 跨书聚合查询 */
crossBookOccurrences(conceptId): {
  book: Book,
  occurrences: Occurrence[]
}[]

// ─── 用户修订 ───

/** 用户校正: 合并/拆分/重命名/修订定义 */
applyRevision(revision: Revision): Result

/** 查询被修订过的历史 */
revisionHistory(targetId): Revision[]

// ─── 诊断 ───

/** 发现书中的问题 (作者矛盾、定义缺失等) */
diagnostics(bookId): Problem[]

// ─── Code Action 类比 ───

/** 对某位置触发操作 */
codeAction(location): Action[]
// Actions 例: '生成复习卡片' / '加入术语表' / '请求 AI 讲解' / ...
```

**所有应用层功能必须通过这套 API 访问 Index**。

---

## 8. 现有功能如何映射

把 `translation-and-glossary-design.md` 里的功能重新表达为 Query：

| 现有功能 | Query Layer 表达 |
|---------|---------------|
| 全书翻译 | `paragraph.forEach(p => translate(p, terms=outline(book)))` |
| 术语识别 | Parser + Extractor 层的标准输出 |
| 术语解释悬浮 | `hover(conceptId)` |
| 术语表视图 | `outline(book)` 或 `workspaceSymbols("*")` |
| 术语用户校正 | `applyRevision({type: 'rename', ...})` |
| 全书术语同步 | `applyRevision({type: 'rename', scope: 'book'})` |

从 "作者原话溯源"讨论延伸出的新功能：

| 功能 | Query |
|------|------|
| 点击术语看首次定义 | `goToDefinition` / `hover` |
| "所有出现"列表 | `findReferences` |
| 分类折叠显示 | `findReferences({types: [...]})` |
| 跳转 + 返回 | `goToDefinition` + 前端栈 |
| 全书术语索引页 | `outline` |

从跨书聚合讨论延伸：

| 功能 | Query |
|------|------|
| "这概念在你读过的其他书也出现过" | `workspaceSymbols` + `crossBookOccurrences` |
| 概念的跨书定义对比 | `crossBookOccurrences` + UI diff |
| 合并/拆分跨书概念 | `applyRevision({type: 'merge'|'split'})` |

---

## 9. 未来功能如何从这个框架生长

### 9.1 Agent 讲解（场景 A）

```
用户选中段落 + 点"讲讲"
  ↓
Agent 调用 Index:
  - documentSymbols(paragraphId)  → 本段涉及的概念
  - callHierarchy 展开              → 前置依赖
  - findReferences for each        → 作者之前讲过什么
  ↓
Agent 基于这些 context 生成讲解
  ↓
讲解中引用的每个概念带回到 Index
```

**关键：Agent 不是"无中生有"，是 Index 上的有 context 生成**。幻觉风险显著降低。

### 9.2 强制回忆 Agent

```
读完章节 →
  concepts = outline(chapter)
  ↓
  对每个 high-importance concept 生成提问
  ↓
  用户回答 → 对比 concept.short_definition
  ↓
  加入 spaced review queue
```

### 9.3 间隔复习 Agent

基于每个 concept 维护 FSRS 记忆强度。
Index 提供跨书的"同一概念"视图 → 同概念的复习自动跨书交错（interleaving effect）。

### 9.4 苏格拉底讨论 Agent

Agent 的 system prompt 自动包含：
- 本书 `outline`
- 用户划线过的 concepts
- 用户有过 elaboration 的 concepts
- 相关跨书 concepts

→ Agent 真的"读过这本书"。

### 9.5 GEO 聚合洞察

所有用户 Index 的聚合统计：
- 哪些 concepts 被最多人查询（高频 = 难点）
- 哪些 concepts 被用户高频修订（作者讲得不清）
- 跨书同 concept 的读者理解分布

**这些数据通用 AI 没有，是 BookReader 独家的 GEO 资产**。

---

## 10. 核心原则

### 原则 1：索引优先，Agent 二等公民

```
先索引, 后生成.
先权威, 后辅助.
先检索, 后推理.

能从 Index 里查到的, 不要让 Agent 重新生成.
Agent 只处理 Index 没有的那部分.
```

### 原则 2：索引可修正

LLM 抽取的 Index **一定有错**。必须：
- 用户能修正每一条
- 修正被持久化
- 相同类错误，系统应当学到不再犯

### 原则 3：索引可信度标注

每条索引数据都带 `confidence`。UI 应当：
- 高置信：正常显示
- 中置信：标"推测"
- 低置信：折叠 + 请求用户确认

### 原则 4：索引增量构建

不要"重新扫全书"。改了一段，只重建受影响的 concept 和 occurrence。

### 原则 5：索引随用户反馈进化

用户每次：
- 点击/悬停 → 轻权重反馈（此 concept 有用）
- 修订 → 强反馈（此抽取错了）
- 跨书合并/拆分 → 最强反馈（概念边界定义）

→ Index 越用越准。这是对静态索引的超越。

### 原则 6：索引是用户资产

用户的 Index + Revisions + Concepts + Merges = 个人知识图谱。

必须：
- 可导出（JSON、Markdown）
- 可备份（用户持有）
- 可迁移（跨设备、跨版本）

---

## 11. 与现有文档的关系

```
agent-and-geo-brainstorm.md  (战略层 / 理论全景)
  ↑
  | 所有 Agent 的养料来自
  |
book-as-indexed-knowledge-base.md  (架构宪法, 本文档)
  |
  | 指导执行层具体设计
  ↓
translation-and-glossary-design.md  (执行层 / MVP)

三者关系:
├── 战略告诉我们 "做什么才有意义"
├── 宪法告诉我们 "底层应该怎么组织"
└── MVP 告诉我们 "先动手做哪一步"
```

本文档引入后，`translation-and-glossary-design.md` 应当在下次迭代时：
1. Schema 部分对齐本文档 §6
2. 把"术语表"改称"Index"
3. 明确 Extractor / Index / Query 的分层
4. 把"原话溯源"作为 `findReferences` 的应用写入

---

## 12. 风险与边界

### 风险 1：LLM 抽取精度

书的语义比代码模糊。Index 精度不会是 100%。

**对策**：
- Confidence 标注
- 用户修正机制
- 对精度敏感的场景（金融公式）要求 Agent 引用原文

### 风险 2：过早抽象

LSP 框架很优雅，但 MVP 不需要完整实现。

**对策**：
- MVP 只做：Paragraphs + Concepts + Occurrences + 最基础的 findReferences/hover/goToDefinition
- Relations、Workspace、Code Action 等按需演化
- 别为了"完备"堆代码

### 风险 3：Schema 早期绑死

Index schema 是基础设施，改起来痛苦。

**对策**：
- 所有表带 `index_version` 字段
- 预留迁移脚本框架
- 前期 schema 变动频繁，用户数据用"可重算"心态（从 EPUB 重建）

### 风险 4：跨书聚合的误合并

见前面讨论：误合并会侵蚀信任。

**对策**：
- 自动合并仅限严格字面匹配
- 语义合并只做"推荐"，不做"执行"
- 所有合并可逆

### 边界：本文档不做什么

- ❌ 不涉及商业模式、会员、用户体系
- ❌ 不涉及具体 UI 设计（交给各 App 层功能设计）
- ❌ 不涉及具体 LLM 选型（见 translation 文档）
- ❌ 不锁定存储技术（SQLite / PostgreSQL / 向量库的选择看部署）

---

## 13. 实施路径建议

重新排一下 MVP 优先级：

### MVP v0: 地基（2-3 周）

```
目标: 对一本书跑通 Parser → Extractor → 最小 Index → 最小 Query

├── EPUB 解析为 paragraphs (稳定 ID)
├── LLM 扫描产出 concepts + occurrences
├── 最简 Query: hover / goToDefinition / findReferences
└── 最简 UI: 术语悬停浮层 + "所有出现"列表

不做: 翻译、Agent、跨书、用户修订
```

### MVP v1: 可用（2-3 周）

```
├── 翻译 (基于现有 Index 保证术语一致)
├── 分类 occurrence (definition / refinement / usage)
├── 用户修订 API (最少: 改名、标错)
└── 术语索引页
```

### MVP v2: 差异化（4-6 周）

```
├── 跨书搜索 + 手动聚合
├── Agent 讲解 (基于 Index context)
├── 概念关系识别
└── Index 导出
```

### MVP v3: 学习 (之后)

```
├── 强制回忆 Agent
├── 间隔复习 Agent
├── 苏格拉底讨论
└── 聚合洞察 / GEO
```

---

## 14. 一句话记住这份文档

> **BookReader 不是一个带 AI 的阅读器。**
> **BookReader 是一个 Book Language Server，加上一个阅读器前端，加上一组基于索引的 Agent。**

所有功能设计都回到一个问题：

**这能不能表达为 Index 上的一次 Query？**

能 → 做到 Query Layer，所有应用都能用。
不能 → 想清楚为什么不能，再考虑做。

---

## 附录 A：完整的 LSP 查询清单（供参考）

代码世界的 LSP 官方查询，凡是对书有意义的都值得思考：

```
textDocument/declaration               跳到声明
textDocument/definition                跳到定义
textDocument/typeDefinition            跳到类型定义
textDocument/implementation            跳到实现
textDocument/references                查找所有引用
textDocument/hover                     悬停信息
textDocument/documentHighlight         当前文档高亮相同符号
textDocument/documentSymbol            文档大纲
textDocument/codeAction                可用操作
textDocument/codeLens                  内嵌信息
textDocument/formatting                格式化
textDocument/rename                    重命名
textDocument/foldingRange              折叠范围
textDocument/selectionRange            选择范围
textDocument/prepareCallHierarchy      调用层级
textDocument/prepareTypeHierarchy      类型层级
textDocument/semanticTokens            语义着色
textDocument/inlayHint                 内嵌提示
textDocument/diagnostic                诊断
workspace/symbol                       跨文件符号搜索
workspace/executeCommand               执行命令
workspace/configuration                配置
```

每一个都能问："书的世界里有对应吗？"——大多数都有。

---

## 附录 B：参考资料

- [LSP Specification](https://microsoft.github.io/language-server-protocol/)
- [Tree-sitter](https://tree-sitter.github.io/) — 语法 Parser 框架，可借鉴到 EPUB Parser
- [Marksman](https://github.com/artempyanykh/marksman) — Markdown LSP，最接近"书 LSP"的现有项目
- [Obsidian Graph View](https://obsidian.md/) — 虽然不是 LSP，但展示了"概念关系图"的产品形态
- [Readwise Reader](https://readwise.io/read) — 商业阅读器里最接近"索引化"思路的产品

---

## 关键决策日志

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-04 | 核心定位：Book Language Server，不是 AI 阅读助手 | 索引化 vs 数字化/聊天化的本质差异 |
| 2026-04 | 四层架构：Parser → Index → Query → Application | 解耦生成与检索；功能都表达为 Query |
| 2026-04 | 索引优先，Agent 二等公民 | 能查到的不让 Agent 重新生成；降低幻觉 |
| 2026-04 | 存储选 SQLite (MVP) → PostgreSQL + pgvector | 强关系数据 + JOIN + 全文搜索；未来向量搜索无缝 |
| 2026-04 | per-book .bookindex 文件组织 | 索引是用户资产，可独立迁移/分享/归档 |
| 2026-04 | 所有 LLM 产出带 confidence | 驱动 UI 可信度标注 + 用户修订优先级 |
| 2026-04 | 跨书聚合"推荐"不"自动执行" | 误合并侵蚀信任，必须用户确认且可逆 |
| 2026-04 | paragraph_id 用 content-hash + 位置签名 | 排版变化不破坏跳转锚点和批注 |
| 2026-04 | 不引入 Neo4j（及可预见规模内） | 图是浅图（1-3 跳），SQL 递归 CTE 足够；真实瓶颈是 FTS 和向量，不是图遍历；未来需要图查询用 Apache AGE 扩展 |
| 2026-04 | relations 表采用节点-边模型 | 向图库迁移零成本，保留未来选项 |

---

## 更新日志

| 日期 | 变更 |
|------|------|
| 2026-04 | 初版起草，建立 Book LSP 概念框架 |
| 2026-04 | §6 加入存储选型小节；加入关键决策日志 |
