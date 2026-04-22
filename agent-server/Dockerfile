FROM python:3.11-slim

WORKDIR /app

# 使用国内镜像源加速 apt-get
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || \
    echo "deb https://mirrors.aliyun.com/debian/ bookworm main" > /etc/apt/sources.list || true

# 安装系统依赖
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 使用国内镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple || \
    pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ || true

# 安装依赖
COPY agent-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制 shared 层 (复用 epub-tts-backend 的 shared)
COPY epub-tts-backend/shared/ /app/shared/

# 复制 agent-server 代码 (逐个复制，跳过 shared symlink)
COPY agent-server/main.py /app/
COPY agent-server/agents/ /app/agents/
COPY agent-server/services/ /app/services/

EXPOSE 9000

CMD ["python", "main.py"]
