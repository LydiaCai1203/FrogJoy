#!/bin/bash
# SSL 配置诊断脚本

echo "=== SSL 证书诊断 ==="
echo ""

# 检查证书文件是否存在
echo "1. 检查证书文件："
if [ -f "ssl/cert.pem" ]; then
    echo "   ✓ cert.pem 存在"
    echo "   文件大小: $(du -h ssl/cert.pem | cut -f1)"
    echo "   文件权限: $(ls -l ssl/cert.pem | awk '{print $1}')"
else
    echo "   ✗ cert.pem 不存在"
fi

if [ -f "ssl/key.pem" ]; then
    echo "   ✓ key.pem 存在"
    echo "   文件大小: $(du -h ssl/key.pem | cut -f1)"
    echo "   文件权限: $(ls -l ssl/key.pem | awk '{print $1}')"
else
    echo "   ✗ key.pem 不存在"
fi

echo ""
echo "2. 检查证书内容："
if [ -f "ssl/cert.pem" ]; then
    echo "   证书数量: $(grep -c "BEGIN CERTIFICATE" ssl/cert.pem)"
    echo "   证书有效期:"
    openssl x509 -in ssl/cert.pem -noout -dates 2>/dev/null || echo "   无法解析证书"
    echo "   证书域名:"
    openssl x509 -in ssl/cert.pem -noout -text 2>/dev/null | grep -A1 "Subject Alternative Name" || openssl x509 -in ssl/cert.pem -noout -subject 2>/dev/null || echo "   无法解析证书"
fi

echo ""
echo "3. 检查 nginx 配置："
if docker ps | grep -q epub-tts-nginx; then
    echo "   ✓ nginx 容器正在运行"
    echo "   测试配置:"
    docker exec epub-tts-nginx nginx -t 2>&1 | head -5
    echo ""
    echo "   检查证书文件是否可访问:"
    docker exec epub-tts-nginx ls -la /etc/nginx/ssl/ 2>&1 || echo "   无法访问证书目录"
else
    echo "   ✗ nginx 容器未运行"
fi

echo ""
echo "4. 测试 SSL 连接："
echo "   使用 openssl 测试（如果可用）:"
echo "   openssl s_client -connect deepkb.com.cn:443 -servername deepkb.com.cn < /dev/null 2>&1 | grep -E 'Verify|Protocol|Cipher'"
echo ""
echo "5. 建议："
echo "   - 确保证书文件权限正确（644 或 600）"
echo "   - 确保证书文件在容器中可访问"
echo "   - 检查防火墙是否允许 443 端口"
echo "   - 使用 SSL Labs 测试: https://www.ssllabs.com/ssltest/analyze.html?d=deepkb.com.cn"

