"""Reading images: find picture paths in what you typed (or dragged into the terminal),
convert iPhone HEIC photos, shrink them, and hand them to a local vision model."""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif", ".tif", ".tiff")
MAX_SIDE = 1536

# Paths like /Users/me/Bilder/IMG_1.HEIC, '/path with space/a.png', /path\ with\ space/a.jpg, ~/x.png
_PATH = re.compile(
    r"""(?:'([^']+?\.(?:%s))'|"([^"]+?\.(?:%s))"|((?:~|/)(?:\\ |[^\s'"])+?\.(?:%s)))(?=$|[\s'",;:!?)])"""
    % ((("|".join(e[1:] for e in IMAGE_EXT)),) * 3),
    re.I,
)


def find_image_paths(text: str) -> list[str]:
    paths = []
    for m in _PATH.finditer(text):
        raw = next(g for g in m.groups() if g)
        p = os.path.expanduser(raw.replace("\\ ", " "))
        if p not in paths:
            paths.append(p)
    return paths


def strip_paths(text: str) -> str:
    """The text without the file paths (what is left is the question about the image)."""
    return re.sub(r"\s+", " ", _PATH.sub(" ", text)).strip()


def _convert_with_sips(src: str, dst: str) -> bool:
    if sys.platform != "darwin" or not shutil.which("sips"):
        return False
    r = subprocess.run(["sips", "-s", "format", "jpeg", "-Z", str(MAX_SIDE), src, "--out", dst],
                       capture_output=True, timeout=30)
    return r.returncode == 0 and os.path.getsize(dst) > 0


def _convert_with_pillow(src: str, dst: str) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        try:
            import pillow_heif  # type: ignore

            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((MAX_SIDE, MAX_SIDE))
            im.save(dst, "JPEG", quality=88)
        return True
    except Exception:
        return False


def load_image_b64(path: str) -> str:
    """Return the image as base64 JPEG/PNG for Ollama. Raises ValueError with a German message."""
    if not os.path.isfile(path):
        raise ValueError(f"Die Datei gibt es nicht: {path}")
    ext = Path(path).suffix.lower()
    size = os.path.getsize(path)
    if ext in (".jpg", ".jpeg", ".png") and size < 4_000_000:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    with tempfile.TemporaryDirectory() as tmp:
        dst = os.path.join(tmp, "bild.jpg")
        if _convert_with_sips(path, dst) or _convert_with_pillow(path, dst):
            with open(dst, "rb") as f:
                return base64.b64encode(f.read()).decode()
    raise ValueError(f"Ich konnte das Bild nicht umwandeln ({ext}).")


VISION_PREFERENCE = ["gemma4:12b", "gemma4", "qwen3.6", "qwen3.5", "qwen2.5vl", "qwen3-vl", "llama3.2-vision",
                     "gemma3", "minicpm-v", "llava"]


def pick_vision_model(llm, installed: list[str], main_model: str) -> str | None:
    """The main model if it can see, otherwise the best installed model that can."""
    def can_see(m: str) -> bool:
        try:
            return "vision" in llm.capabilities(m)
        except Exception:
            return False

    if can_see(main_model):
        return main_model
    ordered = sorted(installed, key=lambda n: next((i for i, p in enumerate(VISION_PREFERENCE) if n.startswith(p)), 99))
    for m in ordered:
        if m != main_model and can_see(m):
            return m
    return None
