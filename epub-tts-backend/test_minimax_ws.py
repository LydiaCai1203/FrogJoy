#!/usr/bin/env python3
"""Test full MiniMax TTS flow with a real voice_id"""
import asyncio
import ssl
import websockets
import json
import sys

async def test_full(api_key: str, voice_id: str, text: str):
    headers = {"Authorization": f"Bearer {api_key}"}
    ws_url = "wss://api.minimaxi.com/ws/v1/t2a_v2"

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    audio_data = b""
    ws = None

    try:
        ws = await websockets.connect(ws_url, additional_headers=headers, ssl=ssl_ctx)
        print('[1] Connected')

        # Receive connection confirmation
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        print(f'[1] recv: {msg}')

        # Send task_start
        await ws.send(json.dumps({
            "event": "task_start",
            "model": "speech-2.8-hd",
            "voice_setting": {
                "voice_id": voice_id,
                "speed": 1.0,
                "vol": 1,
                "pitch": 0,
                "english_normalization": False,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }))
        print('[2] Sent task_start')

        # Receive task_started
        resp = await asyncio.wait_for(ws.recv(), timeout=10)
        print(f'[2] recv: {resp}')

        # Send text
        await ws.send(json.dumps({
            "event": "task_continue",
            "text": text,
        }))
        print(f'[3] Sent text ({len(text)} chars)')

        # Receive audio chunks
        chunk_count = 0
        while True:
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=30)
                data = json.loads(resp)
                if "data" in data and "audio" in data["data"]:
                    audio = data["data"]["audio"]
                    if audio:
                        audio_data += bytes.fromhex(audio)
                        chunk_count += 1
                        print(f'[4] Received chunk {chunk_count}, cumulative bytes: {len(audio_data)}')
                if data.get("is_final"):
                    print(f'[5] is_final received, total chunks: {chunk_count}')
                    break
            except asyncio.TimeoutError:
                print('[!] Timeout waiting for audio data')
                break

        # Send task_finish
        await ws.send(json.dumps({"event": "task_finish"}))
        print(f'[6] Sent task_finish')

        await ws.close()
        print(f'Complete! audio_data={len(audio_data)} bytes')
        return audio_data

    except websockets.exceptions.ConnectionClosedOK as e:
        print(f'[!] ConnectionClosedOK: {e}')
        print(f'    Received so far: {len(audio_data)} bytes')
        return audio_data
    except Exception as e:
        print(f'[!] Error: {type(e).__name__}: {e}')
        return audio_data

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_minimax_ws.py <API_KEY> <VOICE_ID> [TEXT]")
        sys.exit(1)

    api_key = sys.argv[1]
    voice_id = sys.argv[2]
    text = sys.argv[3] if len(sys.argv) > 3 else "你好啊世界，这是一个测试。"

    print(f"Testing voice_id={voice_id}, text={text[:30]}...")
    asyncio.run(test_full(api_key, voice_id, text))
