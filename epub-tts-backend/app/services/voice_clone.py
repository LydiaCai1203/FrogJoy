import aiohttp
import asyncio
import json
import os
import re
from typing import Dict, List, Optional
from loguru import logger

from app.config import settings


class VoiceCloneService:
    """Service for voice cloning operations using MiniMax API"""

    _voices_cache: Optional[List[Dict]] = None

    @staticmethod
    def _get_base_url(base_url_override: Optional[str] = None) -> str:
        return base_url_override or settings.minimax_base_url

    @staticmethod
    async def upload_file(
        api_key: str,
        file_path: str,
        purpose: str,
        base_url: Optional[str] = None,
    ) -> str:
        """
        Upload an audio file to MiniMax API.
        Returns the file_id.
        """
        url = f"{VoiceCloneService._get_base_url(base_url)}/v1/files/upload"
        headers = {"Authorization": f"Bearer {api_key}"}

        with open(file_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("purpose", purpose)
            data.add_field(
                "file",
                f,
                filename=os.path.basename(file_path),
                content_type="audio/mpeg"
            )

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        file_id = result.get("file", {}).get("file_id")
                        if not file_id:
                            raise Exception(f"No file_id in response: {result}")
                        return file_id
                    else:
                        text = await response.text()
                        raise Exception(f"File upload failed: {response.status} - {text}")

    @staticmethod
    async def validate_api_key(api_key: str, base_url: Optional[str] = None) -> bool:
        """Validate MiniMax API key by making a lightweight request."""
        url = f"{VoiceCloneService._get_base_url(base_url)}/v1/files/upload"
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            async with aiohttp.ClientSession() as session:
                # Use a minimal request to check auth — a GET to files endpoint
                # MiniMax doesn't have a dedicated "whoami" endpoint,
                # so we check with a minimal files/list or similar.
                # Actually, the simplest is to just call the upload endpoint
                # without a file — it will return 400 (bad request) if auth is ok,
                # or 401 if auth fails.
                data = aiohttp.FormData()
                data.add_field("purpose", "voice_clone")
                async with session.post(
                    url,
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    # 401/403 = bad key, anything else = key is valid
                    if response.status in (401, 403):
                        return False
                    return True
        except Exception as e:
            logger.warning(f"[VoiceClone] API key validation error: {e}")
            return False

    @staticmethod
    def get_minimax_voices_sync() -> List[Dict]:
        """Get list of MiniMax system voices from JSON file (cached)."""
        if VoiceCloneService._voices_cache is not None:
            return VoiceCloneService._voices_cache

        voices_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "minimax_voices.json"
        )
        try:
            with open(voices_file, "r", encoding="utf-8") as f:
                VoiceCloneService._voices_cache = json.load(f)
        except FileNotFoundError:
            logger.warning(f"[VoiceClone] minimax_voices.json not found at {voices_file}")
            VoiceCloneService._voices_cache = []
        return VoiceCloneService._voices_cache

    @staticmethod
    async def get_minimax_voices(base_url: Optional[str] = None, api_key: Optional[str] = None) -> List[Dict]:
        """Get list of available MiniMax system voices."""
        return VoiceCloneService.get_minimax_voices_sync()

    @staticmethod
    async def clone_voice(
        api_key: str,
        audio_sample_path: str,
        name: str,
        user_id: str,
        lang: str = "zh",
        base_url: Optional[str] = None,
    ) -> Dict:
        """
        Clone a voice using MiniMax API.

        Steps:
        1. Upload the audio sample with purpose='voice_clone' to get file_id
        2. Call voice_clone API with the file_id and voice_id
        """
        effective_base_url = VoiceCloneService._get_base_url(base_url)

        try:
            # Step 1: Upload the audio sample
            logger.info(f"[VoiceClone] Uploading audio sample: {audio_sample_path}")
            file_id = await VoiceCloneService.upload_file(
                api_key=api_key,
                file_path=audio_sample_path,
                purpose="voice_clone",
                base_url=effective_base_url,
            )
            logger.info(f"[VoiceClone] Uploaded file_id: {file_id}")

            # Step 2: Call voice clone API
            # voice_id must be globally unique and ASCII-only — MiniMax rejects non-ASCII
            import uuid
            short_uuid = uuid.uuid4().hex[:8]
            voice_id = f"u_{user_id[:8]}_{short_uuid}"

            clone_url = f"{effective_base_url}/v1/voice_clone"
            clone_payload = {
                "file_id": file_id,
                "voice_id": voice_id,
                "text": "大家好，这是我的克隆音色试听效果，希望听起来自然流畅。",
                "model": "speech-2.8-hd",
            }
            clone_headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    clone_url,
                    headers=clone_headers,
                    json=clone_payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    result_text = await response.text()
                    if response.status == 200:
                        result = json.loads(result_text)
                        logger.info(f"[VoiceClone] Clone result: {result}")

                        # Step 3: Activate the cloned voice via HTTP
                        try:
                            await VoiceCloneService.activate_cloned_voice(
                                api_key=api_key,
                                voice_id=voice_id,
                                base_url=effective_base_url,
                            )
                            logger.info(f"[VoiceClone] Voice {voice_id} activated successfully")
                        except Exception as activate_err:
                            # Activation failure is non-fatal — voice can still be used later
                            logger.warning(f"[VoiceClone] Voice {voice_id} activation failed (will retry on first use): {activate_err}")

                        return {
                            "voice_id": voice_id,
                            "name": name,
                            "lang": lang,
                        }
                    else:
                        logger.error(f"[VoiceClone] Clone API failed: {response.status} - {result_text}")
                        raise Exception(f"Voice clone failed: {response.status} - {result_text}")

        except Exception as e:
            logger.error(f"[VoiceClone] Voice clone error: {e}")
            raise

    # MiniMax WebSocket API limit per task_continue message
    _MINIMAX_CHUNK_SIZE = 2000
    _SENTENCE_SPLIT_PATTERN = re.compile(r'(?<=[。！？.!?\n])')

    @staticmethod
    def _split_text_for_tts(text: str, max_len: int) -> List[str]:
        """Split text into chunks at sentence boundaries, each <= max_len chars."""
        if len(text) <= max_len:
            return [text]

        chunks = []
        remaining = text

        while remaining:
            if len(remaining) <= max_len:
                chunks.append(remaining)
                break

            # Try to split at sentence boundary within max_len
            segment = remaining[:max_len]
            splits = list(VoiceCloneService._SENTENCE_SPLIT_PATTERN.finditer(segment))
            if splits:
                cut = splits[-1].end()
            else:
                # Fallback: split at last comma/space
                cut = max(segment.rfind('，'), segment.rfind(','), segment.rfind(' '), segment.rfind('、'))
                if cut <= 0:
                    cut = max_len

            chunks.append(remaining[:cut])
            remaining = remaining[cut:]

        return [c for c in chunks if c.strip()]

    @staticmethod
    async def generate_speech_minimax(
        api_key: str,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        pitch: int = 0,
        emotion: str = "neutral",
        base_url: Optional[str] = None,
        max_retries: int = 2,
    ) -> bytes:
        """
        Generate speech using MiniMax TTS API via WebSocket.
        Splits long text into chunks to avoid server-side disconnects.
        Includes retry logic for connection drops.
        """
        import ssl
        import websockets

        ws_url = f"{VoiceCloneService._get_base_url(base_url).replace('https://', 'wss://')}/ws/v1/t2a_v2"
        headers = {"Authorization": f"Bearer {api_key}"}

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        text_chunks = VoiceCloneService._split_text_for_tts(
            text, VoiceCloneService._MINIMAX_CHUNK_SIZE
        )
        logger.info(f"[VoiceClone] Text length={len(text)}, split into {len(text_chunks)} chunks")

        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            audio_data = b""
            ws = None
            try:
                ws = await websockets.connect(
                    ws_url,
                    additional_headers=headers,
                    ssl=ssl_context,
                    ping_interval=20,
                    ping_timeout=60,
                    close_timeout=30,
                )
                # 1. Receive connection confirmation
                connected = json.loads(await ws.recv())
                if connected.get("event") != "connected_success":
                    raise Exception(f"WebSocket connection failed: {connected}")
                logger.info(f"[VoiceClone] WebSocket connected (attempt {attempt + 1})")

                # 2. Send task_start
                start_msg = {
                    "event": "task_start",
                    "model": "speech-2.8-hd",
                    "voice_setting": {
                        "voice_id": voice_id,
                        "speed": speed,
                        "vol": 1,
                        "pitch": pitch,
                        "english_normalization": False,
                    },
                    "audio_setting": {
                        "sample_rate": 32000,
                        "bitrate": 128000,
                        "format": "mp3",
                        "channel": 1,
                    },
                }
                await ws.send(json.dumps(start_msg))

                response = json.loads(await ws.recv())
                if response.get("event") != "task_started":
                    raise Exception(f"Task start failed: {response}")

                # 3. Send text in chunks
                for i, chunk in enumerate(text_chunks):
                    logger.debug(f"[VoiceClone] Sending chunk {i+1}/{len(text_chunks)}, len={len(chunk)}")
                    await ws.send(json.dumps({
                        "event": "task_continue",
                        "text": chunk,
                    }))

                # 4. Receive audio chunks (before task_finish)
                while True:
                    try:
                        response = json.loads(await ws.recv())
                    except websockets.exceptions.ConnectionClosedOK:
                        if audio_data:
                            logger.warning(f"[VoiceClone] Connection closed before is_final, returning {len(audio_data)} bytes of partial audio")
                            return audio_data
                        raise

                    if "data" in response and "audio" in response["data"]:
                        audio = response["data"]["audio"]
                        if audio:
                            audio_data += bytes.fromhex(audio)

                    if response.get("is_final"):
                        break

                # 5. Send task_finish after all audio received
                await ws.send(json.dumps({"event": "task_finish"}))

                if not audio_data:
                    raise Exception("MiniMax TTS returned empty audio")

                logger.info(f"[VoiceClone] TTS completed: {len(audio_data)} bytes")
                return audio_data

            except websockets.exceptions.ConnectionClosedOK as e:
                last_error = e
                logger.warning(f"[VoiceClone] Connection closed (attempt {attempt + 1}): {e}")
                if audio_data:
                    return audio_data
            except Exception as e:
                last_error = e
                logger.warning(f"[VoiceClone] TTS attempt {attempt + 1} failed: {e}")
            finally:
                if ws:
                    await ws.close()

        # All retries exhausted
        raise Exception(f"MiniMax TTS failed after {max_retries + 1} attempts: {last_error}")

    @staticmethod
    async def activate_cloned_voice(
        api_key: str,
        voice_id: str,
        base_url: Optional[str] = None,
        max_retries: int = 3,
    ) -> bool:
        """
        Activate a cloned voice by calling MiniMax TTS via HTTP async API once.
        This is required for newly cloned voices before they can be used.
        Returns True if activation succeeded, raises on failure.
        """
        base = VoiceCloneService._get_base_url(base_url)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "speech-2.8-hd",
            "voice_setting": {
                "voice_id": voice_id,
                "speed": 1,
                "vol": 1,
                "pitch": 0,
                "english_normalization": False,
            },
            "audio_setting": {
                "audio_sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
            "text": "音色激活测试。",
            "aigc_watermark": False,
        }

        last_error: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{base}/v1/t2a_async_v2",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            task_id = result.get("task_id")
                            if task_id:
                                # Poll for result
                                audio = await VoiceCloneService._poll_async_result(
                                    session, base, api_key, task_id, headers, max_wait=60
                                )
                                if audio:
                                    logger.info(f"[VoiceClone] Voice {voice_id} activated successfully")
                                    return True
                            else:
                                # Sync response — activation succeeded
                                logger.info(f"[VoiceClone] Voice {voice_id} activated (sync response)")
                                return True
                        elif resp.status in (401, 403):
                            raise Exception(f"MiniMax API auth failed: {resp.status}")
                        else:
                            text_err = await resp.text()
                            last_error = Exception(f"HTTP {resp.status}: {text_err}")
                            logger.warning(f"[VoiceClone] Activation attempt {attempt + 1} failed: {last_error}")
            except Exception as e:
                last_error = e
                logger.warning(f"[VoiceClone] Activation attempt {attempt + 1} error: {e}")

        raise Exception(f"Voice activation failed after {max_retries + 1} attempts: {last_error}")

    @staticmethod
    async def _poll_async_result(
        session: aiohttp.ClientSession,
        base: str,
        api_key: str,
        task_id: str,
        headers: dict,
        max_wait: int = 60,
    ) -> Optional[bytes]:
        """Poll MiniMax async TTS result until audio is ready."""
        import time
        poll_interval = 2
        elapsed = 0
        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            try:
                async with session.get(
                    f"{base}/v1/t2a_async_result",
                    headers=headers,
                    params={"task_id": task_id},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        status = result.get("status")
                        logger.info(f"[VoiceClone] Poll status={status}")
                        if status == "completed":
                            audio_hex = result.get("data", {}).get("audio") or result.get("audio")
                            if audio_hex:
                                return bytes.fromhex(audio_hex)
                            # No audio but completed — still considered success for activation
                            return b""
                        elif status == "failed":
                            raise Exception(f"Async task failed: {result}")
                        # still pending, continue polling
                    else:
                        logger.warning(f"[VoiceClone] Poll HTTP {resp.status}")
            except Exception as e:
                if "failed" in str(e).lower():
                    raise
                logger.warning(f"[VoiceClone] Poll error: {e}")
        raise Exception(f"Async TTS polling timed out after {max_wait}s")
