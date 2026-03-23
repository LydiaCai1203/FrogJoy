# 📚 BookReader

[![GitHub](https://img.shields.io/badge/GitHub-Repository-black?logo=github)](https://github.com/LydiaCai1203/BookReader)

> 一款轻量级 EPUB 阅读器 Web 应用，支持文字阅读与 AI 语音朗读
>
> 🔗 **GitHub**: https://github.com/LydiaCai1203/BookReader

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6?logo=typescript&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

### 💰 完全免费

当前版本使用 **Microsoft Edge TTS** 引擎，无需 API Key，无需付费，完全白嫖微软的高质量语音合成服务！

---

## ✨ 功能亮点

| 功能 | 描述 |
|------|------|
| 📖 **文字阅读** | 智能分句、章节导航、阅读进度追踪 |
| 🎧 **在线语音** | 基于 Microsoft Edge TTS，14+ 种中文音色可选 |
| 🎯 **逐词高亮** | 播放时实时高亮当前朗读的词语 |
| ⚡ **音频缓存** | 已生成的音频自动缓存，无需重复生成 |
| 📥 **离线下载** | 支持整本书音频下载，断点续传 |
| 📚 **书架管理** | 上传的书籍自动保存，随时继续阅读 |

---

## 🛠️ 技术栈

### 后端 (Backend)

| 技术 | 用途 |
|------|------|
| **Python 3.10+** | 运行环境 |
| **FastAPI** | Web 框架，高性能异步 API |
| **edge-tts** | 微软 Edge TTS 引擎，免费语音合成 |
| **ebooklib** | EPUB 文件解析 |
| **BeautifulSoup4** | HTML 内容提取 |
| **langdetect** | 自动语言检测 |

### 前端 (Frontend)

| 技术 | 用途 |
|------|------|
| **React 18** | UI 框架 |
| **TypeScript** | 类型安全 |
| **Vite** | 构建工具 |
| **TailwindCSS** | 样式框架 |
| **shadcn/ui** | UI 组件库 |
| **TanStack Query** | 数据请求管理 |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- pnpm / npm

### 1. 启动后端

```bash
cd epub-tts-backend

# 创建虚拟环境（首次）
python -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 启动服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动前端

```bash
cd epub-tts-frontend

# 安装依赖
npm install

# 方式一：开发模式（热更新，适合开发）
npm run dev

# 方式二：生产模式（构建后预览，适合部署）
npm run build
npm run preview
```

### 3. 访问应用

- 本机访问：[http://localhost:8888](http://localhost:8888)
- 局域网访问：`http://<你的IP>:8888`（同一网络内的其他设备）

> 💡 **生产部署**：运行 `npm run build` 后，可将 `dist/` 目录部署到任意静态服务器（Nginx、Caddy、Vercel 等）

---

## 📁 项目结构

```
ett/
├── epub-tts-backend/          # 后端服务
│   ├── app/
│   │   ├── main.py            # 应用入口
│   │   ├── api.py             # API 路由
│   │   └── services/          # 业务逻辑
│   │       ├── book_service.py    # 书籍管理
│   │       ├── tts_service.py     # 语音合成
│   │       └── task_service.py    # 后台任务
│   └── data/                  # 数据存储（已 gitignore）
│       ├── books/             # 上传的 EPUB 文件
│       ├── audio/             # 生成的音频缓存
│       └── covers/            # 书籍封面
│
└── epub-tts-frontend/         # 前端应用
    └── src/
        ├── components/        # UI 组件
        ├── api/               # API 服务层
        └── pages/             # 页面组件
```

---

## 🎨 界面预览

### 上传书籍
![上传书籍](./upload.png)

### 阅读界面
![阅读界面](./content.png)

### 音频下载
![音频下载](./download.png)

### LLM 翻译配置
![LLM配置](./llm%20config.png)

---

## 🗺️ Roadmap

### 已完成 ✅

- [x] EPUB 解析与阅读
- [x] Microsoft Edge TTS 语音合成（免费）
- [x] 多种中文音色选择
- [x] 逐词高亮跟读
- [x] 音频缓存与离线下载
- [x] 断点续传
- [x] 书架管理

### 计划中 🚧

**📖 阅读体验**
- [ ] **多语言支持** - 外语书籍阅读
- [ ] **LLM 智能翻译** - 接入大语言模型，实时翻译外语内容
- [ ] **PDF 支持** - 扩展文档格式支持

**🎙️ 语音引擎**
- [ ] **高级 TTS 服务** - 支持更多语音服务商
  - [ ] OpenAI TTS
  - [ ] Azure Speech
  - [ ] ElevenLabs
  - [ ] Fish Audio
- [ ] **流行音色** - 更自然、更有表现力的 AI 音色
- [ ] **语音克隆** - 自定义专属音色

**📚 书架与社区**
- [ ] **书籍共享** - 用户上传的书籍支持公开共享，构建共享书库
- [ ] **智能分类** - 基于 AI 的书籍自动分类与标签
- [ ] **高级检索** - 支持全文搜索、标签筛选、智能推荐
- [ ] **阅读统计** - 阅读时长、进度追踪、阅读习惯分析
- [ ] **用户系统** - 账号登录、云端同步、多设备阅读进度

**💎 高级功能（付费）**
- [ ] **知识图谱生成** - 基于 LLM 分析书籍内容，自动生成知识图谱
  - 概念关系可视化
  - 人物关系网络
  - 事件脉络梳理
- [ ] **跨书观点对比** - 对比不同书籍对同一主题的观点与论述
- [ ] **思维导图** - AI 自动生成章节/全书思维导图
- [ ] **核心观点提取** - 智能总结每章及全书核心论点
- [ ] **智能读书笔记** - AI 辅助生成笔记，关联知识图谱
- [ ] **学习路径推荐** - 基于知识图谱，推荐相关书籍的最佳阅读顺序
- [ ] **引用网络** - 分析书中引用来源，构建学术引用关系图

---

## 📝 License

MIT License © 2024

---

## 🤝 Contributing

欢迎提交 Issue 和 Pull Request！
