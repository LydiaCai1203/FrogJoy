#!/usr/bin/env python3
"""Test MiniMax TTS HTTP API"""
import asyncio
import aiohttp
import json

async def test():
    api_key = input("Enter MiniMax API Key: ").strip()
    if not api_key:
        print("No API key provided")
        return

    headers = {"Authorization": f"Bearer {api_key}"}

    # Try a simple HTTP request to the base URL
    base_url = "https://api.minimaxi.com"
    try:
        async with aiohttp.ClientSession() as session:
            # Try fetching the root or a known endpoint
            resp = await session.get(f"{base_url}/", headers=headers, timeout=aiohttp.ClientTimeout(total=10))
            print(f"GET / -> status={resp.status}")
            text = await resp.text()
            print(f"Body (first 200 chars): {text[:200]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    # Try WebSocket upgrade manually
    import ssl
    import websockets

    ws_url = "wss://api.minimaxi.com/ws/v1/t2a_v2"
    try:
        ws = await websockets.connect(ws_url, additional_headers=headers, ssl=ssl.create_default_context())
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        print(f"WebSocket connected: {msg}")
        await ws.close()
    except Exception as e:
        print(f"WebSocket Error: {type(e).__name__}: {e}")

asyncio.run(test())
