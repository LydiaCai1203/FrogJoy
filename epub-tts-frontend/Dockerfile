# 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app

# 配置 npm 使用国内镜像源（淘宝镜像）
RUN npm config set registry https://registry.npmmirror.com || true

# 复制 package 文件
COPY package*.json ./

# 安装依赖
RUN npm ci --prefer-offline --no-audit

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 生产阶段
FROM nginx:alpine

# 复制构建产物到 nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置（如果有自定义配置）
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动 nginx
CMD ["nginx", "-g", "daemon off;"]

