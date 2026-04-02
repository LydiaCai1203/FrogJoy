# B站音频下载与人声分离指南

## 1. 获取音频 URL

在 B站 视频页面打开开发者工具，执行：

```javascript
window.__playinfo__.data.dash.audio[0].baseUrl
```

这会返回音频的直链 URL。

## 2. 下载音频

```bash
curl '音频URL' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' \
  -H 'referer: https://www.bilibili.com/video/BV号/' \
  --compressed -o audio.m4s -Lv
```

## 3. 格式转换 (m4s → mp3)

```bash
ffmpeg -i audio.m4s -c:a libmp3lame -q:a 2 audio.mp3
```

## 4. 截取片段

```bash
ffmpeg -i audio.m4s -ss 19:05 -to 19:20 -c:a libmp3lame -q:a 2 clip.mp3
```

## 5. 安装人声分离工具

```bash
pip install demucs torchcodec
```

## 6. AI 分离人声

```bash
demucs --two-stems=vocals clip.mp3
```

输出目录：`separated/htdemucs/clip/`
- `vocals.wav` - 人声
- `no_vocals.wav` - 背景音乐

## 7. 导出人声 MP3

```bash
ffmpeg -i vocals.wav -c:a libmp3lame -q:a 2 vocals_only.mp3
```

## 依赖工具

| 工具 | 安装方式 |
|------|----------|
| ffmpeg | `brew install ffmpeg` |
| demucs | `pip install demucs torchcodec` |
