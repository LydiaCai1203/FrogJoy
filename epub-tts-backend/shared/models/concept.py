from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey, Index, func
from shared.models import Base


class Concept(Base):
    """
    书籍中的核心概念（术语、人名、理论等）。

    由 ConceptService Phase 1+2 提取并去重后写入。
    频次统计字段在 Phase 3 完成后回填。
    parent_concept_id 指向更上位的概念 (如"向上流动" -> "社会流动"),
    Phase 2 LLM linker 设置, 用于 Phase 3 span 仲裁和前端展示。
    """
    __tablename__ = "concepts"

    id          = Column(String, primary_key=True)                          # concept:{uuid4}
    book_id     = Column(String, ForeignKey("books.id"), nullable=False)
    user_id     = Column(String, ForeignKey("users.id"), nullable=False)

    term        = Column(String, nullable=False)                            # 规范名
    aliases     = Column(JSON, nullable=False, server_default="[]")         # 别名列表
    category    = Column(String, nullable=False)                            # term/term_custom/person/work/theory
    initial_definition = Column(Text, nullable=True)                        # 作者原文解释 (弹窗展示)
    parent_concept_id  = Column(String, ForeignKey("concepts.id"), nullable=True)

    # 频次统计 (Phase 3 后回填)
    total_occurrences = Column(Integer, nullable=False, server_default="0")
    chapter_count     = Column(Integer, nullable=False, server_default="0") # 出现在几个章节
    scope             = Column(String, nullable=False, server_default="chapter")  # book / chapter

    created_at  = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_concepts_user_book", "user_id", "book_id"),
        Index("idx_concepts_parent", "parent_concept_id"),
    )


class ConceptOccurrence(Base):
    """
    概念在段落中的出现记录。

    occurrence_type:
      - definition: 作者在此处定义/解释概念
      - refinement: 作者在此处深化/补充/举例
      - mention: 顺带提及, 未展开

    core_sentence: 作者原文核心句 (仅 definition/refinement),
                   用于悬浮弹窗展示。
    """
    __tablename__ = "concept_occurrences"

    id               = Column(String, primary_key=True)                         # occ:{uuid4}
    concept_id       = Column(String, ForeignKey("concepts.id"), nullable=False)
    paragraph_id     = Column(String, ForeignKey("indexed_paragraphs.id"), nullable=False)
    user_id          = Column(String, nullable=False)
    book_id          = Column(String, nullable=False)
    chapter_idx      = Column(Integer, nullable=False)

    occurrence_type  = Column(String, nullable=False)                           # definition/refinement/mention
    matched_text     = Column(Text, nullable=True)                              # 匹配的原文片段
    core_sentence    = Column(Text, nullable=True)                              # 弹窗展示用核心句
    reasoning        = Column(Text, nullable=True)                              # LLM 标注理由

    created_at       = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_occ_user_book", "user_id", "book_id"),
        Index("idx_occ_concept", "concept_id"),
        Index("idx_occ_paragraph", "paragraph_id"),
        Index("idx_occ_user_book_chapter", "user_id", "book_id", "chapter_idx"),
    )


class ConceptEvidence(Base):
    """
    概念的强证据 (verbatim quote).

    由 Phase 1 LLM 直接给出, 经服务端校验 (quote 逐字 in paragraph,
    term/alias in quote) 才落库. 用于:
      - definition / refinement 类型的角标位置 (matched_text == quote)
      - 弹窗展示作者原话核心句

    与 ConceptOccurrence 的分工:
      ConceptEvidence: 强证据 (definition/refinement), LLM grounded
      ConceptOccurrence: 弱出现 (mention), Phase 3 regex 补全
    前端 get_chapter_annotations 把两表 UNION 后输出 occurrences.
    """
    __tablename__ = "concept_evidence"

    id           = Column(String, primary_key=True)                          # ev:{uuid4}
    concept_id   = Column(String, ForeignKey("concepts.id"), nullable=False)
    paragraph_id = Column(String, ForeignKey("indexed_paragraphs.id"), nullable=False)
    user_id      = Column(String, nullable=False)
    book_id      = Column(String, nullable=False)
    chapter_idx  = Column(Integer, nullable=False)

    quote        = Column(Text, nullable=False)            # 原文逐字片段
    role         = Column(String, nullable=False)          # definition / refinement
    char_offset  = Column(Integer, nullable=False)         # quote 在段落中的起始位置
    char_length  = Column(Integer, nullable=False)

    created_at   = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_ev_user_book", "user_id", "book_id"),
        Index("idx_ev_user_book_chapter", "user_id", "book_id", "chapter_idx"),
        Index("idx_ev_concept", "concept_id"),
        Index("idx_ev_paragraph", "paragraph_id"),
    )
