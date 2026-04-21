# Backend Refactor Design Spec

**Date**: 2026-04-21
**Scope**: epub-tts-backend + admin-backend 全面重构
**Goal**: 解决文件臃肿、职责耦合、模型重复三大问题，API 路径同步整理

---

## 0. 核心约束：零功能回归

**所有现有功能已经过人工测试，重构必须保证行为完全不变。**

- **纯结构性重构**：只做搬移代码、拆分文件、整理 import，不改任何业务逻辑
- **逐模块迁移**：每完成一个模块，确保该模块所有路由的请求/响应行为与重构前一致
- **保留原始逻辑**：即使看到可以"优化"的代码，也不在本次重构中修改。错误处理、边界条件、默认值等全部原样搬迁
- **API 路径映射**：新旧 API 路径有清晰的一一对应关系，前端同步更新调用路径即可，不改请求/响应格式
- **数据库结构重构**：合并碎片化偏好表、规范化 AI 配置表、修正数据类型，通过 Alembic migration 脚本迁移数据

---

## 1. 表结构重构

### 1.1 合并偏好表 → `user_preferences`

**删除**: `user_theme_preferences`, `voice_preferences`, `user_ai_preferences`, `user_feature_setup`
**新建**: `user_preferences`

```
user_preferences
├── user_id              PK, FK → users.id
│
│ -- 主题 (原 user_theme_preferences) --
├── theme                String, default="eye-care"
├── font_size            Integer, default=18
│
│ -- 语音 (原 voice_preferences) --
├── active_voice_type    String, default="edge"
├── active_edge_voice    String, default="zh-CN-XiaoxiaoNeural"
├── active_minimax_voice String, nullable
├── active_cloned_voice_id String, nullable
├── speed                Integer, default=100
├── pitch                Integer, default=0
├── emotion              String, default="neutral"
├── audio_persistent     Boolean, default=False
│
│ -- AI (原 user_ai_preferences) --
├── enabled_ask_ai       Boolean, default=False
├── enabled_translation  Boolean, default=False
├── translation_mode     String, default="current-page"
├── source_lang          String, default="Auto"
├── target_lang          String, default="Chinese"
├── translation_prompt   Text, nullable
│
│ -- 时间戳 --
├── created_at           DateTime
└── updated_at           DateTime
```

`UserFeatureSetup` 删除，feature 是否已配置从数据推导：
- `ai_chat_configured` → `ai_provider_configs` 存在且 purpose="chat"
- `voice_synthesis_configured` → `tts_provider_configs` 存在且 api_key_encrypted 非空

### 1.2 `ReadingStat.date` String → Date

```sql
ALTER TABLE reading_stats ALTER COLUMN date TYPE date USING date::date;
```

### 1.3 `ai_model_configs` → `ai_provider_configs` 多行表

**删除**: `ai_model_configs` (chat+translation 混在一行)
**新建**: `ai_provider_configs`

```
ai_provider_configs
├── id                   PK, String (uuid)
├── user_id              FK → users.id
├── purpose              String  ("chat" / "translation")
├── provider_type        String  ("openai-chat" / "anthropic")
├── base_url             String
├── api_key_encrypted    String
├── model                String
├── created_at           DateTime
└── updated_at           DateTime

UniqueConstraint(user_id, purpose)
Index(user_id)
```

### 1.4 迁移策略

一个 Alembic migration `016_refactor_preferences_and_ai.py`:
1. 创建 `user_preferences`，从 4 张旧表 SELECT INSERT 合并，删除旧表
2. ALTER `reading_stats.date` 类型
3. 创建 `ai_provider_configs`，从 `ai_model_configs` 拆行迁移，删除旧表

---

## 2. 共享层 `shared/`

两个后端共用的基础设施，是 models 和 schemas 的唯一真相源。

```
epub-tts-backend/shared/
├── __init__.py
├── config.py              # Settings（从现有 app/config.py 迁移）
├── database.py            # engine, SessionLocal, get_db()
├── redis_client.py        # Redis 连接
├── models/
│   ├── __init__.py        # re-export Base 和所有 model
│   ├── user.py            # User (无 UserFeatureSetup)
│   ├── book.py            # Book
│   ├── highlight.py       # Highlight
│   ├── reading.py         # ReadingStat (date 为 Date 类型), ReadingProgress
│   ├── ai.py              # AIProviderConfig, BookTranslation
│   ├── tts.py             # TTSProviderConfig, ClonedVoice
│   ├── preferences.py     # UserPreferences (合并后的偏好表)
│   ├── index.py           # IndexedBook, IndexedParagraph
│   └── system.py          # SystemSetting
└── schemas/
    ├── __init__.py
    ├── auth.py            # LoginRequest, RegisterRequest, TokenResponse
    ├── book.py            # BookOut, BookListOut
    ├── tts.py             # TTSRequest, PrefetchRequest, DownloadRequest, ...
    ├── tts_config.py      # TTSConfigIn/Out, VoicePreferenceIn/Out
    ├── ai.py              # AIModelConfigIn/Out, ChatRequest, TranslateRequest, ...
    ├── reading.py         # ReadingProgressIn/Out, ReadingStatsOut
    ├── highlight.py       # HighlightIn/Out
    ├── index.py           # IndexRequest/Response
    └── task.py            # TaskOut
```

**要点**:
- `Base` 定义在 `shared/models/__init__.py`，只有一份
- 现有 `app/models/models.py`（356 行）按领域拆成小文件
- 散落在各 router 里的 Pydantic schemas 全部集中到 `shared/schemas/`
- 模型名变化：`AIModelConfig` → `AIProviderConfig`，`VoicePreferences`+`UserThemePreferences`+`UserAIPreferences` → `UserPreferences`，删除 `UserFeatureSetup`

---

## 2. 主后端路由层 `app/routers/`

每个路由文件只做参数校验 + 调用 service + 返回响应，不包含业务逻辑。

```
app/routers/
├── auth.py              # 注册/登录/验证
├── books.py             # 书籍 CRUD
├── tts.py               # /tts/speak, /tts/prefetch
├── tts_download.py      # /tts/download/*, /books/{id}/download-audio*
├── tts_cache.py         # /tts/cache/*
├── tts_config.py        # /tts/config, /tts/providers/status
├── voices.py            # /voices/*, /voices/preferences
├── ai_config.py         # /ai/config, /ai/preferences, /ai/models
├── ai_chat.py           # /ai/chat
├── ai_translate.py      # /ai/translate/*
├── highlights.py        # 高亮标注
├── reading.py           # reading_progress + reading_stats 合并
├── files.py             # 静态文件服务
├── index.py             # 索引相关
└── tasks.py             # 任务管理
```

**公共依赖** `app/deps.py`:
```python
def get_book_owner(book_id, current_user_id) -> str: ...
def get_book_title(book_id, user_id) -> str: ...
def is_audio_persistent(user_id) -> bool: ...
def get_minimax_credentials(user_id) -> tuple[str, str|None]: ...
```

---

## 3. 主后端服务层 `app/services/`

```
app/services/
├── tts/
│   ├── __init__.py
│   ├── edge.py           # EdgeTTSProvider：Edge TTS 生成逻辑
│   ├── minimax.py        # MinimaxTTSProvider：MiniMax 生成 + 语音克隆
│   ├── cache.py          # AudioCache：磁盘缓存索引
│   ├── memory.py         # AudioMemoryCache：内存 LRU 缓存
│   ├── router_service.py # TTSFacade：按 voice_type 路由到 edge/minimax，统一缓存
│   └── download.py       # BookAudioDownloader：整书下载后台任务
├── ai/
│   ├── __init__.py
│   ├── provider.py       # AIService, OpenAIChatProvider, AnthropicProvider
│   └── translation.py    # TranslationService：章节/整书翻译后台任务
├── book.py               # BookService（EPUB 解析）
├── auth.py               # AuthService（JWT + 加解密）
├── email.py              # EmailService
├── task.py               # TaskManager
├── index.py              # IndexService
└── system_settings.py    # get_system_setting()
```

**拆分映射**:

| 现有代码 | 目标位置 | 约行数 |
|---------|---------|-------|
| tts_service.py AudioCache | tts/cache.py | ~180 |
| tts_service.py AudioMemoryCache | tts/memory.py | ~160 |
| tts_service.py TTSService（Edge 部分） | tts/edge.py | ~200 |
| tts_service.py TTSService（MiniMax 分支）+ voice_clone.py | tts/minimax.py | ~350 |
| tts_service.py generate_audio() 路由逻辑 | tts/router_service.py | ~100 |
| api.py generate_book_audio_task() | tts/download.py | ~200 |
| api.py generate_book_audio_zip_task() | tts/download.py | ~150 |
| ai.py _run_book_translation() | ai/translation.py | ~100 |

---

## 4. Admin 后端

```
admin-backend/app/
├── main.py
├── dependencies.py
├── routers/
│   ├── auth.py
│   ├── users.py
│   ├── dashboard.py
│   └── settings.py
└── schemas/             # admin 专有 schemas（保留）
    ├── user.py
    ├── dashboard.py
    └── settings.py
```

**变化**:
- 删除 `app/models.py` → `from shared.models import User, Book, ReadingStat, Highlight, SystemSetting`
- 删除 `app/database.py` → `from shared.database import get_db, engine`
- 删除 `app/config.py` → `from shared.config import settings`
- 删除 `app/redis_client.py` → `from shared.redis_client import redis_client`

**import 方式**: admin-backend 启动时通过 `sys.path` 引入 shared，Docker 构建时 COPY shared/ 进 admin 镜像。

---

## 5. API 路径设计

```
# === 认证 ===
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/verify-email

# === 书籍 ===
GET    /api/books
POST   /api/books
GET    /api/books/{book_id}
DELETE /api/books/{book_id}
GET    /api/books/{book_id}/toc
GET    /api/books/{book_id}/chapters/{chapter_href}
GET    /api/books/{book_id}/cover

# === TTS 播放 ===
POST   /api/tts/speak
POST   /api/tts/prefetch

# === TTS 缓存 ===
GET    /api/tts/cache/stats?book_id=
GET    /api/tts/cache/chapter?book_id=&chapter_href=
DELETE /api/tts/cache?book_id=

# === TTS 下载 ===
POST   /api/tts/download/chapter
POST   /api/books/{book_id}/download-audio
POST   /api/books/{book_id}/download-audio-zip
GET    /api/files/audio/{book_id}/{filename}
GET    /api/files/audio/tmp/{filename}

# === TTS 配置 ===
GET    /api/tts/config
PUT    /api/tts/config
DELETE /api/tts/config
GET    /api/tts/providers/status

# === 音色 ===
GET    /api/voices
GET    /api/voices/edge
GET    /api/voices/minimax
POST   /api/voices/clone
GET    /api/voices/cloned
DELETE /api/voices/cloned/{voice_id}
GET    /api/voices/preferences
PUT    /api/voices/preferences

# === AI 配置 ===
GET    /api/ai/config
PUT    /api/ai/config
GET    /api/ai/preferences
PUT    /api/ai/preferences
GET    /api/ai/models

# === AI 功能 ===
POST   /api/ai/chat
POST   /api/ai/translate/chapter
POST   /api/ai/translate/book
GET    /api/ai/translate/{book_id}/chapter?chapter_href=&target_lang=
GET    /api/ai/translate/{book_id}

# === 阅读 ===
GET    /api/reading/progress/{book_id}
PUT    /api/reading/progress/{book_id}
GET    /api/reading/stats
POST   /api/reading/stats/record

# === 高亮 ===
GET    /api/highlights/{book_id}
POST   /api/highlights
DELETE /api/highlights/{highlight_id}

# === 索引 ===
POST   /api/index/books/{book_id}/parse
GET    /api/index/books/{book_id}/status
GET    /api/index/books/{book_id}/paragraphs

# === 任务 ===
GET    /api/tasks
GET    /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
```

**主要变化**:
- 音色从 `/tts/voices/*` 独立到 `/voices/*`
- 文件下载统一走 `/files/audio/`，不再暴露 user_id
- 阅读进度和统计合并到 `/reading/`
- 任务管理独立 `/tasks` 前缀

---

## 6. Alembic 迁移

### env.py 调整
```python
# 之前
from app.models.models import Base
# 之后
from shared.models import Base
```

### 新增 migration: `016_refactor_preferences_and_ai.py`

**Upgrade 逻辑**:
1. 创建 `user_preferences` 表
2. 从 `user_theme_preferences`、`voice_preferences`、`user_ai_preferences` SELECT INSERT 合并数据到 `user_preferences`（LEFT JOIN on user_id）
3. 删除 `user_theme_preferences`、`voice_preferences`、`user_ai_preferences`、`user_feature_setup`
4. ALTER `reading_stats.date` 从 String 改为 Date（`USING date::date`）
5. 创建 `ai_provider_configs` 表
6. 从 `ai_model_configs` 迁移数据：每行拆成 1-2 行（chat 必有，translation 可选）
7. 删除 `ai_model_configs`

**Downgrade 逻辑**: 反向操作（创建旧表、迁移数据回去、删除新表）

`alembic/` 目录位置不变，主后端启动时执行 `alembic upgrade head`。

---

## 7. 文件迁移清单

### 新建
- `shared/` 整个目录
- `app/deps.py`
- `app/routers/tts.py`, `tts_download.py`, `tts_cache.py`, `voices.py`
- `app/routers/ai_config.py`, `ai_chat.py`, `ai_translate.py`
- `app/routers/reading.py`, `tasks.py`
- `app/services/tts/` 整个目录
- `app/services/ai/` 整个目录

### 删除
- `app/models/models.py` → 拆到 shared/models/
- `app/models/database.py` → 移到 shared/database.py
- `app/models/user.py` → 移到 shared/models/user.py
- `app/config.py` → 移到 shared/config.py
- `app/redis_client.py` → 移到 shared/redis_client.py
- `app/api.py` → 拆到多个 router + service
- `app/services/tts_service.py` → 拆到 services/tts/
- `app/services/voice_clone.py` → 合并到 services/tts/minimax.py
- `app/routers/reading_progress.py` + `reading_stats.py` → 合并到 routers/reading.py
- `app/services/reading_progress_service.py` + `reading_stats_service.py` → 可合并或保留
- `admin-backend/app/models.py` → 删除，改用 shared
- `admin-backend/app/database.py` → 删除，改用 shared
- `admin-backend/app/config.py` → 删除，改用 shared
- `admin-backend/app/redis_client.py` → 删除，改用 shared

### 不变
- `app/parsers/` (epub_parser.py, paragraph_id.py)
- `app/middleware/` (auth.py, rate_limit.py)
- `alembic/versions/` (所有 migration 文件)
- 前端代码（需要同步更新 API 调用路径）
