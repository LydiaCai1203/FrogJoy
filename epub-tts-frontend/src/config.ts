// API 配置
// 通过 nginx 代理，使用相对路径或当前域名

const getApiBase = () => {
  const { protocol, hostname, port } = window.location;
  
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return `${protocol}//${hostname}:8000`;
  }
  
  if (port === '8888' || port === '5173') {
    return `${protocol}//${hostname}:8000`;
  }
  
  return `${protocol}//${hostname}:${port}`;
};

export const API_BASE = getApiBase();
export const API_URL = `${API_BASE}/api`;
