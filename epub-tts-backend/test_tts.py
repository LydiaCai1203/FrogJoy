#!/usr/bin/env python3
"""
测试 edge-tts 是否正常工作，并查看返回的数据结构

运行: python test_tts.py
"""
import asyncio
import edge_tts

async def test_tts():
    print("测试 edge-tts...")
    print(f"edge-tts 版本: {edge_tts.__version__ if hasattr(edge_tts, '__version__') else '未知'}")
    
    text = "你好，这是一个测试。今天天气真不错。"
    voice = "zh-CN-XiaoxiaoNeural"  # 中文女声
    
    print(f"\n文本: {text}")
    print(f"语音: {voice}")
    print("\n--- 数据流块 ---")
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        
        audio_chunks = []
        word_boundaries = []
        
        async for chunk in communicate.stream():
            chunk_type = chunk.get("type", "unknown")
            print(f"Chunk type: {chunk_type}")
            
            if chunk_type == "audio":
                data = chunk.get("data", b"")
                audio_chunks.append(data)
                print(f"  Audio data length: {len(data)} bytes")
            elif chunk_type == "WordBoundary":
                print(f"  Full chunk: {chunk}")
                word_boundaries.append(chunk)
            else:
                print(f"  Full chunk: {chunk}")
        
        print(f"\n--- 汇总 ---")
        print(f"音频块数量: {len(audio_chunks)}")
        print(f"音频总大小: {sum(len(c) for c in audio_chunks)} 字节")
        print(f"字词边界数量: {len(word_boundaries)}")
        
        if word_boundaries:
            print(f"\n--- 字词边界示例 ---")
            print(f"第一个字词边界: {word_boundaries[0]}")
            
            # 检查字段名
            sample = word_boundaries[0]
            print(f"\n可用字段: {list(sample.keys())}")
        
        # 保存测试音频
        if audio_chunks:
            with open("test_output.mp3", "wb") as f:
                for chunk in audio_chunks:
                    f.write(chunk)
            print(f"\n测试音频已保存到: test_output.mp3")
        
        print("\n✅ edge-tts 工作正常!")
        
    except Exception as e:
        print(f"\n❌ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tts())

