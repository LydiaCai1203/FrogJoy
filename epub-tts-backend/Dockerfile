FROM python:3.11-slim

WORKDIR /app

# 使用国内镜像源加速 apt-get（如果网络慢）
# 检测并替换 Debian 源为阿里云镜像
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || \
    echo "deb https://mirrors.aliyun.com/debian/ bookworm main" > /etc/apt/sources.list || true

# 安装系统依赖（增加超时和重试机制）
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 使用阿里云镜像源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（增加超时和重试）
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p data/users data/images

# 添加 entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 暴露端口
EXPOSE 8000

# 启动命令
ENTRYPOINT ["/entrypoint.sh"]

