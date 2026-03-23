# Nginx 配置说明

## 概述

Nginx 已经通过 Docker Compose 自动配置，**不需要单独下载或安装**。

## 工作原理

1. **自动下载镜像**：`docker-compose up` 会自动从 Docker Hub 拉取 `nginx:alpine` 镜像
2. **配置文件挂载**：`nginx/nginx.conf` 会被挂载到容器内的 `/etc/nginx/conf.d/default.conf`
3. **自动启动**：容器启动时 nginx 会自动运行

## 配置文件位置

- **本地配置文件**：`./nginx/nginx.conf`
- **容器内路径**：`/etc/nginx/conf.d/default.conf`

## 常用操作

### 1. 启动服务（自动拉取 nginx 镜像）

```bash
# 在项目根目录执行
docker-compose up -d
```

### 2. 修改配置后重新加载

```bash
# 方法1：重启 nginx 容器（推荐）
docker-compose restart nginx

# 方法2：重新加载配置（不中断服务）
docker exec epub-tts-nginx nginx -s reload

# 方法3：测试配置是否正确
docker exec epub-tts-nginx nginx -t
```

### 3. 查看 nginx 日志

```bash
# 查看实时日志
docker-compose logs -f nginx

# 查看最近100行日志
docker-compose logs --tail=100 nginx
```

### 4. 进入 nginx 容器调试

```bash
docker exec -it epub-tts-nginx sh
# 进入后可以执行：
# nginx -t          # 测试配置
# nginx -s reload   # 重新加载
# cat /etc/nginx/conf.d/default.conf  # 查看配置
```

## 配置说明

### 当前配置

- **域名**：`deepkb.com.cn` 和 `www.deepkb.com.cn`
- **HTTP 端口**：80
- **HTTPS 端口**：443（已预留，需要 SSL 证书）

### 修改域名

编辑 `nginx/nginx.conf`，修改 `server_name` 行：

```nginx
server_name your-domain.com www.your-domain.com;
```

然后重新加载配置：

```bash
docker-compose restart nginx
```

### 启用 HTTPS

1. 将 SSL 证书放到 `nginx/ssl/` 目录：
   ```bash
   mkdir -p nginx/ssl
   # 将证书文件复制到该目录
   cp your-cert.pem nginx/ssl/cert.pem
   cp your-key.pem nginx/ssl/key.pem
   ```

2. 在 `docker-compose.yml` 中取消注释 SSL 卷挂载：
   ```yaml
   volumes:
     - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
     - ./nginx/ssl:/etc/nginx/ssl:ro  # 取消注释这行
   ```

3. 在 `nginx/nginx.conf` 中取消注释 HTTPS server 块

4. 重启服务：
   ```bash
   docker-compose restart nginx
   ```

## 故障排查

### 检查配置语法

```bash
docker exec epub-tts-nginx nginx -t
```

### 查看错误日志

```bash
docker-compose logs nginx | grep error
```

### 检查端口占用

```bash
# 检查 80 端口是否被占用
sudo lsof -i :80
# 或
sudo netstat -tulpn | grep :80
```

## 注意事项

1. **配置文件权限**：确保 `nginx.conf` 文件可读
2. **端口冲突**：确保 80 和 443 端口未被其他服务占用
3. **域名解析**：确保域名已正确解析到服务器 IP
4. **防火墙**：确保防火墙允许 80 和 443 端口访问

