# 全书概念提取 + 悬浮释义 设计文档

> **目标**：基于已有的全书段落索引，提取书中核心概念，构建概念知识网络；用户阅读时悬浮概念即可看到作者原文解释，无需翻回前文。
>
> 日期：2026-04-21

---

## 0. TL;DR

1. 全书逐章扫描提取概念，跨章去重合并
2. 回到全书段落做语义匹配，统计概念 × 章节频次矩阵
3. 用频次和共现关系做聚类，客观判定书级主题和章级重点
4. 阅读界面中概念可悬浮，弹窗展示作者原文中对该概念的解释
5. 成本方案：LLM 提取用 Minimax 降本，匹配阶段可用 embedding

---

## 1. 前置依赖

已完成的 LSP v0 提供：

- `indexed_paragraphs` 表：全书所有段落，带稳定 ID、章节归属、原文
- `indexed_books` 表：书籍元数据、索引状态
- EPUB Parser：EPUB → 章节 → 段落的解析能力

本方案在此基础上新增**概念层**。

---

## 2. 概念提取流程

### 2.1 Step 1：全书逐章扫描

对每一章独立调用 LLM，输入：

- 本章全部段落（从 `indexed_paragraphs` 取）
- 全书目录（所有章节标题，提供全书语境）

输出每章的概念列表：

```json
{
  "term": "有条件养育",
  "aliases": ["有条件的爱"],
  "category": "term_custom",
  "first_occurrence_pid": "isbn:xxx:ch01:003f",
  "reasoning": "本书书名概念，与无条件养育形成核心对立"
}
```

分类体系（5 类）：
- `term` — 学科通用术语（如"强化"）
- `term_custom` — 作者自创/特定术语（如"有条件养育"）
- `person` — 被引用的人物（如"斯金纳"）
- `work` — 被引用的作品
- `theory` — 理论体系（如"行为主义心理学"）

**注意**：此阶段不需要 LLM 打 confidence 分，后续用频次数据客观判定。

### 2.2 Step 2：跨章去重合并

各章独立提取会产生重复（第1章提取了"行为主义"，第3章也提取了）。

合并策略：
- 完全同名 → 直接合并
- 别名匹配 → 合并（"有条件的爱" = "有条件养育"）
- embedding 相似度 > 阈值 → 人工或 LLM 确认后合并

产出：**全书统一概念表**。

### 2.3 Step 3：全书段落匹配 + 频次统计

拿统一概念表回到 `indexed_paragraphs`，对每个段落检测包含了哪些概念。

匹配方式：
- 关键词 + 别名精确匹配（快，覆盖大部分情况）
- embedding 语义匹配（补充同义表述、换了说法的情况）

对每次匹配，标注 **occurrence 类型**：
- `definition` — 作者在定义/解释这个概念
- `refinement` — 作者在深化、补充、举例说明
- `mention` — 顺带提及，未展开

产出：**概念 × 章节 频次矩阵**

```
              第1章  第2章  第3章  ...  第10章  总计
有条件养育      8     3     5          2      18
行为主义        6     1     0          0       7
撤回爱          1    12     3          0      16
```

### 2.4 Step 4：知识结构推导

从频次矩阵自动得出两层结构：

**书级主题**：跨多章高频出现的概念
- 判定标准：出现章节数 ≥ 总章节数的 50%，或总频次排名前 N

**章级重点**：在某章内高频但全书不普遍的概念
- 判定标准：该章内频次占全书总频次的 60% 以上

### 2.5 Step 5：概念聚类

按**共现关系**聚类——经常在同一段落出现的概念归为一簇：

```
簇 A「行为主义批判」: 斯金纳, 行为主义, 强化, 有条件养育
簇 B「人本主义」: 卡尔·罗杰斯, 无条件养育, 自我价值感
簇 C「养育后果」: 假我, 撤回爱, 情感虐待
```

聚类方法：
- 构建概念共现图（同段落出现 → 加边）
- 社区发现算法（如 Louvain）或简单的层次聚类

---

## 3. 悬浮释义交互

### 3.1 用户体验

概念旁边出现一个小圆圈角标（类似脚注标记），圆圈内是编号：

```
有条件养育 ① 是指家长对孩子的爱出于"他们做了什么"……
后来斯金纳 ② 提出的强化理论 ③ 更是将这种模式理论化……
```

- 桌面端：鼠标悬浮角标 → 弹出气泡弹窗
- 移动端：轻触角标 → 弹出气泡弹窗

角标编号按概念在本章中首次出现的顺序排列。同一概念在本章内只在首次出现时显示角标。

### 3.2 弹窗内容

展示的是**作者原文中对该概念的解释**，不是 AI 总结。

内容来源：从该概念的所有 occurrences 中，筛选 type = `definition` 或 `refinement` 的段落，取最核心的 1-2 段作者原文。

示例：

```
┌─────────────────────────────────────────┐
│  有条件养育                              │
│                                         │
│  「家长对孩子的爱出于'他们做了什么'——    │
│  孩子只有在做到家长期望或达到所规定的     │
│  标准后才能得到爱。」                    │
│                         —— 第1章 第3段   │
│                                         │
│  查看原文位置 →                          │
└─────────────────────────────────────────┘
```

如果作者在多处有不同角度的解释，最多展示 2 段，按章节顺序排列。

### 3.3 阅读进度感知（防剧透）

弹窗**只展示当前章及之前章节中的解释**。

理由：非虚构书常逐步展开论证，提前看到后续章节的深化解释可能破坏阅读节奏。

实现：查询 occurrences 时加条件 `chapter_idx <= 当前章节`。

### 3.4 原文摘录长度控制

作者的一段解释可能有 300 字，弹窗放不下。策略：

- 优先选最短且完整的定义段落
- 若段落过长（> 150 字），用 LLM 预处理时提取该段的**核心句**（1-2 句）
- 核心句在索引构建时预生成，不在悬浮时实时调用

### 3.5 角标密度控制

一段话里可能同时出现多个概念，角标过多会干扰阅读。

策略：
- 同一概念在本章只标注首次出现
- 默认只标注**该章重点概念**（章级重点，由 Step 4 判定）
- 用户可在设置中调整：全部标注 / 仅重点 / 关闭

---

## 4. 数据模型（新增）

### 4.1 concepts 表

```sql
CREATE TABLE concepts (
  id          VARCHAR PRIMARY KEY,    -- concept:{uuid}
  book_id     VARCHAR NOT NULL,
  user_id     VARCHAR NOT NULL,
  term        VARCHAR NOT NULL,       -- 概念名称
  aliases     JSON DEFAULT '[]',      -- 别名列表
  category    VARCHAR NOT NULL,       -- term/term_custom/person/work/theory
  cluster_id  VARCHAR,                -- 所属概念簇
  total_occurrences INTEGER DEFAULT 0,
  chapter_count     INTEGER DEFAULT 0, -- 出现在几个章节中
  scope       VARCHAR DEFAULT 'chapter', -- 'book' 或 'chapter' 级别
  created_at  DATETIME DEFAULT NOW(),

  FOREIGN KEY (book_id) REFERENCES books(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 4.2 concept_occurrences 表

```sql
CREATE TABLE concept_occurrences (
  id          VARCHAR PRIMARY KEY,
  concept_id  VARCHAR NOT NULL,
  paragraph_id VARCHAR NOT NULL,      -- 关联 indexed_paragraphs.id
  user_id     VARCHAR NOT NULL,
  book_id     VARCHAR NOT NULL,
  chapter_idx INTEGER NOT NULL,
  occurrence_type VARCHAR NOT NULL,   -- definition/refinement/mention
  core_sentence   TEXT,               -- 预提取的核心句（用于弹窗展示）
  created_at  DATETIME DEFAULT NOW(),

  FOREIGN KEY (concept_id) REFERENCES concepts(id),
  FOREIGN KEY (paragraph_id) REFERENCES indexed_paragraphs(id)
);
```

### 4.3 concept_clusters 表

```sql
CREATE TABLE concept_clusters (
  id          VARCHAR PRIMARY KEY,
  book_id     VARCHAR NOT NULL,
  user_id     VARCHAR NOT NULL,
  name        VARCHAR,                -- 簇名（如"行为主义批判"）
  concept_ids JSON NOT NULL,          -- 包含的概念 ID 列表
  created_at  DATETIME DEFAULT NOW()
);
```

---

## 5. 构建流程（与现有索引的衔接）

```
用户点击「构建索引」
  ↓
[已有] EPUB 解析 → indexed_paragraphs 入库
  ↓
[新增] 全书逐章概念扫描（LLM, Minimax）
  ↓
[新增] 跨章去重合并 → concepts 入库
  ↓
[新增] 全书段落匹配 + occurrence_type 标注 → concept_occurrences 入库
  ↓
[新增] 频次统计 + 聚类 → 更新 concepts.scope / cluster_id
  ↓
[新增] 预生成弹窗用 core_sentence
  ↓
状态: parsed → enriched
```

索引状态扩展：`pending → parsing → parsed → enriching → enriched → failed`

---

## 6. 成本估算

以《无条件养育》（10章，~500段）为例，使用 Minimax：

| 步骤 | 调用次数 | 估算成本 |
|------|---------|---------|
| Step 1 逐章概念扫描 | 10 次 LLM 调用 | 低 |
| Step 2 去重合并 | 1 次 LLM 或纯算法 | 极低 |
| Step 3 段落匹配 | embedding 或关键词 | 极低 |
| Step 3 occurrence_type 标注 | 批量 LLM 调用 | 中（主要成本） |
| Step 5 聚类 | 纯算法 | 无 LLM 成本 |
| 预生成 core_sentence | 仅对 definition/refinement 段落 | 低 |

---

## 7. 待决策项

1. **embedding 模型选型** — 用 Minimax embedding 还是其他？需要支持中英文
2. **occurrence_type 标注精度** — 是否需要原型验证？区分 definition 和 mention 的准确率直接影响弹窗质量
3. **聚类粒度** — 簇太大失去意义，太小等于没聚。需要在真实数据上调参
4. **移动端交互** — 移动端无 hover，改为轻触弹窗，交互细节待设计

---

## 8. 下一步

1. **occurrence_type 标注原型验证** — 用《无条件养育》第1章已提取的 13 个概念，验证 definition/refinement/mention 分类准确率
2. **数据库 migration** — 新增 concepts、concept_occurrences、concept_clusters 三张表
3. **Step 1-3 后端实现** — 概念提取 + 匹配 pipeline
4. **前端悬浮弹窗 prototype** — 先做静态 mock，验证交互体验
