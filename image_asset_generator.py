"""Codex /generate-image client. Preserve PNG bytes and never remove backgrounds."""

import base64
import binascii
import hashlib
import io
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from token_usage import track_request

from PIL import Image

import plant_kurzge as config  # Loads the existing .env without modifying it.

MAX_BYTES = 20 * 1024 * 1024


def image_config():
    base = os.getenv("IMAGE_API_BASE_URL", "").strip()
    if not base:
        parts = urlsplit(config.API_URL or "")
        base = urlunsplit(parts._replace(path="/generate-image", query="", fragment=""))
    parts = urlsplit(base)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.path.rstrip("/") != "/generate-image":
        raise ValueError("IMAGE_API_BASE_URL phải là URL đầy đủ của /generate-image.")
    model = os.getenv("IMAGE_MODEL") or config.MODEL
    if not model:
        raise ValueError("Thiếu IMAGE_MODEL hoặc CODEX_MODEL.")
    return {"url": base, "model": model,
            "key": os.getenv("IMAGE_API_KEY") or config.API_KEY,
            "quality": os.getenv("IMAGE_QUALITY", "medium")}


def validate_png(data, *, transparent=False, expected_size=None):
    """Check real PNG decoding, dimensions, alpha channel and visible content."""
    if len(data) > MAX_BYTES or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Ảnh phải là PNG hợp lệ, tối đa 20 MiB.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG" or image.is_animated:
                raise ValueError("Asset phải là một PNG tĩnh.")
            if not all(1 <= n <= 8192 for n in image.size):
                raise ValueError(f"Kích thước PNG không hợp lệ: {image.size}.")
            if expected_size and tuple(expected_size) != image.size:
                raise ValueError(f"Kích thước PNG {image.size}, cần {tuple(expected_size)}.")
            image.load()
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            alpha = image.convert("RGBA").getchannel("A")
            lo, hi = alpha.getextrema()
            if hi == 0:
                raise ValueError("PNG hoàn toàn trong suốt, không có nội dung.")
            if transparent and (not has_alpha or lo != 0):
                raise ValueError("Asset cần nền trong suốt nhưng PNG không có vùng alpha=0. "
                                 "Yêu cầu sinh lại PNG có alpha thật; không tự xóa nền.")
            return {"size": list(image.size), "mode": image.mode, "has_alpha": has_alpha,
                    "alpha_range": [lo, hi], "content_bbox": list(alpha.getbbox())}
    except (OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValueError(f"PNG không giải mã được: {error}") from error


class ImageAssetGenerator:
    def __init__(self, cache_dir, configuration=None):
        self.cache_dir = Path(cache_dir)
        self.config = configuration if configuration is not None else image_config()

    def generate(self, prompt, *, transparent, requested_size, offline=False):
        # The endpoint accepts ONLY prompt and model. Image options belong in the prompt.
        full_prompt = (prompt + f"\nRequested PNG canvas: {requested_size[0]}x{requested_size[1]} pixels."
                       + f"\nDetail preference: {self.config['quality']}. "
                       + ("Real transparent alpha background, including empty margins. No checkerboard."
                          if transparent else "Opaque background. No transparent margins."))
        recipe = {"version": 1, "endpoint": self.config["url"], "model": self.config["model"],
                  "prompt": full_prompt, "transparent": transparent, "requested_size": list(requested_size)}
        key = hashlib.sha256(json.dumps(recipe, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        path = self.cache_dir / f"{key}.png"
        meta_path = path.with_suffix(".json")
        if path.is_file() and meta_path.is_file():
            data = path.read_bytes()
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                meta = {}
            if meta.get("recipe") == recipe and meta.get("sha256") == hashlib.sha256(data).hexdigest():
                return path, {**validate_png(data, transparent=transparent), "cache_key": key, "cached": True}
        if offline:
            raise ValueError(f"Chưa có cache PNG hợp lệ: {key}. Cần gọi generate_image để sinh ảnh.")
        if not self.config.get("key"):
            raise ValueError("Thiếu IMAGE_API_KEY hoặc CODEX_API_TOKEN.")
        request = Request(self.config["url"], method="POST",
                          data=json.dumps({"prompt": full_prompt, "model": self.config["model"]}).encode(),
                          headers={"Content-Type": "application/json", "x-api-key": self.config["key"]})
        try:
            with track_request() as observe:
                with urlopen(request, timeout=660) as response:
                    # Base64 adds ~1/3 overhead. Bound the JSON response too.
                    raw = response.read(MAX_BYTES * 2 + 1)
                if len(raw) > MAX_BYTES * 2:
                    raise ValueError("Response ảnh vượt giới hạn.")
                payload = json.loads(raw)
                observe(payload)
        except HTTPError as error:
            raise ValueError(f"/generate-image trả HTTP {error.code}; kiểm tra model, API key và server.") from error
        except (URLError, TimeoutError) as error:
            raise ValueError(f"Không kết nối được /generate-image: {error}. Chưa thể kiểm tra sinh ảnh thực tế.") from error
        try:
            if not isinstance(payload, dict):
                raise ValueError("/generate-image phải trả một JSON object.")
            if payload.get("success") is False:
                raise ValueError("/generate-image báo sinh ảnh thất bại.")
            data = base64.b64decode(payload["data"][0]["b64_json"], validate=True)
        except (KeyError, IndexError, TypeError, binascii.Error) as error:
            raise ValueError("/generate-image cần trả data[0].b64_json chứa PNG base64.") from error
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            info = validate_png(data, transparent=transparent)
        except ValueError:
            # Keep the original for diagnosis, but never mark it as a usable cache entry.
            (self.cache_dir / f"{key}.rejected.png").write_bytes(data)
            raise
        path.write_bytes(data)
        meta_path.write_text(json.dumps({"recipe": recipe, "sha256": hashlib.sha256(data).hexdigest(),
                                        "validation": info}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path, {**info, "cache_key": key, "cached": False}
