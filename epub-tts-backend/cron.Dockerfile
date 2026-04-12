FROM python:3.11-slim

WORKDIR /app

# 使用国内镜像源加速 apt-get
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || \
    echo "deb https://mirrors.aliyun.com/debian/ bookworm main" > /etc/apt/sources.list || true

RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 使用国内镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple || \
    pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ || true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 只需要 cron 服务相关代码
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

# 复制 cron 启动脚本
COPY cron_entrypoint.sh /cron_entrypoint.sh
RUN chmod +x /cron_entrypoint.sh

ENTRYPOINT ["/cron_entrypoint.sh"]
