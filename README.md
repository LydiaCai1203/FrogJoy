# BookReader

一款轻量级 EPUB 阅读器 Web 应用，支持文字阅读与 AI 语音朗读

**在线体验：https://deepkb.com.cn**

[![GitHub](https://img.shields.io/badge/GitHub-Repository-black?logo=github)](https://github.com/LydiaCai1203/BookReader)
![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6?logo=typescript&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 功能与优势

| 功能 | 说明 |
|------|------|
| **阅读** | EPUB 解析、章节导航、进度追踪、书籍自动保存 |
| **语音朗读** | Edge TTS 免费语音、14+ 音色可选、实时高亮、音频缓存、离线下载 |
| **高亮批注** | 文本高亮、批注笔记、笔记列表统一管理 |
| **AI 助手** | 选中内容提问、AI 智能解答 |
| **数据统计** | 阅读热力图、阅读时长、习惯分析 |
| **多端同步** | PostgreSQL 数据持久化，随时继续阅读 |

---

## 技术栈

### 后端
- Python 3.10+ / FastAPI / edge-tts / ebooklib / SQLAlchemy / PostgreSQL

### 前端
- React 18 / TypeScript / Vite / TailwindCSS / shadcn/ui / TanStack Query / epubjs

---

## 界面预览

### 首页
![首页](./assets/首页.png)

### 朗读支持多音色选择
![朗读支持多音色选择](./assets/朗读支持多音色选择.png)

### 阅读模式同步高亮笔记
![阅读模式同步高亮笔记](./assets/阅读模式同步高亮笔记.png)

### 高亮和批注
![高亮和批注](./assets/高亮和批注.png)

### 笔记列表
![笔记列表](./assets/笔记列表.png)

### 阅读热力图
![阅读热力图](./assets/阅读热力图.png)

### 问 AI
![问AI](./assets/问AI.png)

---

## 快速部署

### 环境要求

- Docker & Docker Compose

### 启动服务

```bash
# 克隆项目后，进入项目目录
cd /workspace

# 启动所有服务（数据库 + 后端 + 前端 + Nginx）
docker-compose up -d

# 查看服务状态
docker-compose ps
```

### 访问应用

- Nginx 代理端口：**80**
- 访问地址：`http://localhost`

### 服务架构

| 服务 | 端口 | 说明 |
|------|------|------|
| nginx | 80, 443 | 反向代理 |
| frontend | 80 (nginx) | React 前端 |
| backend | 8000 (internal) | FastAPI 后端 |
| db | 5432 (internal) | PostgreSQL 数据库 |

### 停止服务

```bash
docker-compose down
```

### 重新构建

```bash
docker-compose up -d --build
```

---

## 项目结构

```
/workspace/
├── assets/                    # README 图片资源
├── epub-tts-backend/          # 后端服务
│   ├── app/
│   │   ├── main.py            # 应用入口
│   │   ├── api.py             # API 路由
│   │   ├── routers/           # 路由模块
│   │   ├── services/          # 业务逻辑
│   │   └── models/            # 数据模型
│   └── data/                  # 数据存储
│       ├── books/             # EPUB 文件
│       ├── audio/             # 音频缓存
│       └── images/            # 用户图片
├── epub-tts-frontend/         # 前端应用
│   └── src/
│       ├── components/        # UI 组件
│       ├── pages/             # 页面
│       └── api/               # API 服务
├── docker-compose.yml         # 容器编排
└── nginx/                     # Nginx 配置
```

---

## Star History

<a href="https://www.star-history.com/?repos=LydiaCai1203%2FBookReader&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=LydiaCai1203/BookReader&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=LydiaCai1203/BookReader&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=LydiaCai1203/BookReader&type=timeline&legend=top-left" />
 </picture>
</a>

---

## License

**禁止商业使用**

本项目仅供个人学习与研究使用，未经授权不得用于任何商业目的。

MIT License
