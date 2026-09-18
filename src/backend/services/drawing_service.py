"""
Drawing and canvas processing service.

What this module does *for real* with only Pillow + NumPy:

* decodes canvas PNGs (raw base64 or ``data:image/...;base64,`` URLs),
* measures ink coverage, bounding box and connected-component count,
* classifies individual strokes geometrically (line / circle / rectangle /
  freeform) from their point lists,
* enhances and re-encodes images.

Symbol/equation recognition needs a vision model. When none is loaded the
service reports ``available: False`` with an explanation instead of returning
made-up equations.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from config.settings import get_settings
from services.common import utc_now_iso

logger = logging.getLogger(__name__)

MAX_ANALYSIS_SIDE = 1024  # analysis resolution; keeps numpy work under ~1M pixels


class DrawingDecodeError(ValueError):
    """The submitted data was not a decodable image."""


def decode_image(drawing_data: str, max_bytes: Optional[int] = None) -> Image.Image:
    """Decode base64 (optionally a data URL) into a PIL image."""
    if not isinstance(drawing_data, str) or not drawing_data.strip():
        raise DrawingDecodeError("No image data supplied")
    payload = drawing_data.strip()
    if payload.startswith("data:"):
        try:
            _, payload = payload.split(",", 1)
        except ValueError as exc:
            raise DrawingDecodeError("Malformed data URL") from exc
    try:
        raw = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise DrawingDecodeError("Image data is not valid base64") from exc
    if max_bytes is not None and len(raw) > max_bytes:
        raise DrawingDecodeError(f"Image is larger than the {max_bytes} byte limit")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:
        raise DrawingDecodeError("Data is not a supported image") from exc
    return image


def _encode_png(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class DrawingService:
    """Canvas image analysis and stroke geometry."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("Drawing service ready (Pillow %s)", Image.__version__)

    async def cleanup(self) -> None:
        self.is_initialized = False

    def is_healthy(self) -> bool:
        return self.is_initialized

    # ------------------------------------------------------------------ #
    # Image analysis
    # ------------------------------------------------------------------ #

    def _ink_mask(self, image: Image.Image) -> np.ndarray:
        """Boolean mask of 'ink' pixels; transparent or light pixels are background."""
        if max(image.size) > MAX_ANALYSIS_SIDE:
            ratio = MAX_ANALYSIS_SIDE / max(image.size)
            image = image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))))
        rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        alpha = rgba[..., 3]
        gray = rgba[..., :3].mean(axis=2)
        return (alpha > 32) & (gray < 200)

    @staticmethod
    def _count_components(mask: np.ndarray) -> int:
        """Connected components (4-neighbourhood) via iterative flood fill on a coarse grid."""
        if not mask.any():
            return 0
        # Downsample aggressively; we only need a rough count of separate marks.
        step = max(1, max(mask.shape) // 128)
        coarse = mask[::step, ::step]
        h, w = coarse.shape
        seen = np.zeros_like(coarse, dtype=bool)
        count = 0
        ys, xs = np.nonzero(coarse)
        for start_y, start_x in zip(ys, xs):
            if seen[start_y, start_x]:
                continue
            count += 1
            stack = [(start_y, start_x)]
            seen[start_y, start_x] = True
            while stack:
                y, x = stack.pop()
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < h and 0 <= nx < w and coarse[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        return count

    def analyze_image(self, image: Image.Image) -> Dict[str, Any]:
        mask = self._ink_mask(image)
        ink_pixels = int(mask.sum())
        total = int(mask.size)
        result: Dict[str, Any] = {
            "is_blank": ink_pixels == 0,
            "ink_coverage": round(ink_pixels / total, 5) if total else 0.0,
            "components": self._count_components(mask),
            "bounding_box": None,
        }
        if ink_pixels:
            ys, xs = np.nonzero(mask)
            scale_x = image.width / mask.shape[1]
            scale_y = image.height / mask.shape[0]
            result["bounding_box"] = {
                "x": int(xs.min() * scale_x),
                "y": int(ys.min() * scale_y),
                "width": int((xs.max() - xs.min() + 1) * scale_x),
                "height": int((ys.max() - ys.min() + 1) * scale_y),
            }
        return result

    async def process_drawing(
        self,
        drawing_data: str,
        process_type: str = "equation_recognition",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Decode and analyse a canvas image. Recognition is reported honestly."""
        started = time.perf_counter()
        image = decode_image(drawing_data, self.settings.max_upload_size)
        stats = self.analyze_image(image)

        if stats["is_blank"]:
            message = "The canvas is empty."
        else:
            message = (
                "Symbol recognition requires the Qwen3-Omni vision model, which is not loaded. "
                "Type the expression in the chat box or load the model from Settings."
            )

        return {
            "data": {
                "equations": [],
                "shapes": [],
                "text": "",
                "confidence": 0.0,
                "available": False,
                "message": message,
                "image_analysis": stats,
            },
            "confidence": 0.0,
            "processing_time": time.perf_counter() - started,
            "process_type": process_type,
            "image_dimensions": {"width": image.width, "height": image.height},
            "timestamp": utc_now_iso(),
        }

    # ------------------------------------------------------------------ #
    # Stroke geometry
    # ------------------------------------------------------------------ #

    @staticmethod
    def _points(stroke: Dict[str, Any]) -> np.ndarray:
        pts = stroke.get("points") or []
        coords: List[Tuple[float, float]] = []
        for p in pts:
            if isinstance(p, dict) and "x" in p and "y" in p:
                coords.append((float(p["x"]), float(p["y"])))
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                coords.append((float(p[0]), float(p[1])))
        return np.asarray(coords, dtype=float) if coords else np.empty((0, 2))

    def classify_stroke(self, stroke: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Classify a stroke as line / circle / rectangle / freeform from its points."""
        pts = self._points(stroke)
        if len(pts) < 3:
            return None
        min_xy, max_xy = pts.min(axis=0), pts.max(axis=0)
        width, height = (max_xy - min_xy).tolist()
        span = max(width, height, 1e-9)
        if span < self.settings.drawing_min_stroke_length:
            return None
        bbox = {"x": float(min_xy[0]), "y": float(min_xy[1]), "width": float(width), "height": float(height)}

        # Straightness: max distance from the chord between endpoints, relative to span.
        start, end = pts[0], pts[-1]
        chord = end - start
        chord_len = float(np.linalg.norm(chord))
        if chord_len > 1e-9:
            dists = np.abs(np.cross(chord, pts - start)) / chord_len
            straightness = float(dists.max() / span)
        else:
            straightness = 1.0
        if straightness < 0.05 and chord_len > 0.8 * span:
            return {"type": "line", "confidence": round(1.0 - straightness * 10, 3), "bounding_box": bbox,
                    "length": chord_len, "angle_degrees": math.degrees(math.atan2(chord[1], chord[0]))}

        closed = chord_len < 0.2 * span
        if closed:
            center = (min_xy + max_xy) / 2
            radii = np.linalg.norm(pts - center, axis=1)
            mean_r = float(radii.mean())
            if mean_r > 0:
                radial_var = float(radii.std() / mean_r)
                aspect = min(width, height) / span
                if radial_var < 0.15 and aspect > 0.75:
                    return {"type": "circle", "confidence": round(1.0 - radial_var * 4, 3), "bounding_box": bbox,
                            "center": {"x": float(center[0]), "y": float(center[1])}, "radius": mean_r}
                # Rectangle: most points hug the bounding box edges
                dx = np.minimum(np.abs(pts[:, 0] - min_xy[0]), np.abs(pts[:, 0] - max_xy[0]))
                dy = np.minimum(np.abs(pts[:, 1] - min_xy[1]), np.abs(pts[:, 1] - max_xy[1]))
                on_edge = float(np.mean(np.minimum(dx, dy) < 0.08 * span))
                if on_edge > 0.8:
                    return {"type": "rectangle", "confidence": round(on_edge, 3), "bounding_box": bbox}
            return {"type": "closed_curve", "confidence": 0.6, "bounding_box": bbox}

        return {"type": "freeform", "confidence": 0.5, "bounding_box": bbox, "point_count": int(len(pts))}

    async def analyze_strokes(self, strokes: List[Dict[str, Any]], analysis_type: str = "shape_recognition") -> Dict[str, Any]:
        shapes = [s for s in (self.classify_stroke(stroke) for stroke in strokes) if s]
        confidence = float(np.mean([s["confidence"] for s in shapes])) if shapes else 0.0
        return {
            "shapes": shapes,
            "equations": [],
            "confidence": round(confidence, 3),
            "stroke_count": len(strokes),
            "analysis_type": analysis_type,
            "timestamp": utc_now_iso(),
        }

    async def analyze_canvas_state(self, canvas_data: str, canvas_objects: List[Dict[str, Any]]) -> Dict[str, Any]:
        result = await self.process_drawing(canvas_data, "equation_recognition")
        types: Dict[str, int] = {}
        for obj in canvas_objects or []:
            kind = str(obj.get("type", "unknown"))
            types[kind] = types.get(kind, 0) + 1
        stats = result["data"]["image_analysis"]
        suggestions: List[str] = []
        if stats["is_blank"]:
            suggestions.append("Draw or write something on the canvas first.")
        else:
            if stats["ink_coverage"] < 0.002:
                suggestions.append("Write larger: very little of the canvas is used, which hurts recognition.")
            if stats["components"] > 40:
                suggestions.append("The canvas is crowded; clear it between problems for best results.")
        return {
            "analysis": {"image_analysis": result["data"], "object_analysis": {"object_count": len(canvas_objects or []), "types": types}},
            "suggestions": suggestions,
            "timestamp": utc_now_iso(),
        }

    # ------------------------------------------------------------------ #
    # Image utilities
    # ------------------------------------------------------------------ #

    async def enhance_drawing(self, drawing_data: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        options = options or {}
        image = decode_image(drawing_data, self.settings.max_upload_size)
        enhanced = image.convert("RGBA")
        applied: List[str] = []
        if options.get("contrast_enhancement", True):
            enhanced = ImageEnhance.Contrast(enhanced).enhance(1.5)
            applied.append("contrast_enhancement")
        if options.get("noise_reduction", True):
            enhanced = enhanced.filter(ImageFilter.MedianFilter(size=3))
            applied.append("noise_reduction")
        if options.get("sharpening", True):
            enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
            applied.append("sharpening")
        return {
            "enhanced_data": _encode_png(enhanced),
            "enhancements": applied,
            "image_analysis": self.analyze_image(enhanced),
            "timestamp": utc_now_iso(),
        }

    async def convert_to_latex(self, drawing_data: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = await self.process_drawing(drawing_data, "equation_recognition", options)
        return {
            "latex": [],
            "confidence": 0.0,
            "available": False,
            "message": result["data"]["message"],
            "timestamp": utc_now_iso(),
        }

    async def validate_equation(self, drawing_data: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = await self.process_drawing(drawing_data, "equation_recognition", options)
        stats = result["data"]["image_analysis"]
        return {
            "is_valid": False,
            "equation": "",
            "validation_errors": ["The canvas is empty."] if stats["is_blank"] else ["Equation recognition is unavailable without the vision model."],
            "suggestions": ["Type the equation in the chat box to have it solved."],
            "confidence": 0.0,
            "timestamp": utc_now_iso(),
        }

    async def export_drawing(self, drawing_data: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        options = options or {}
        image = decode_image(drawing_data, self.settings.max_upload_size)
        export_data: Dict[str, str] = {"png": _encode_png(image)}
        if options.get("include_jpeg", True):
            buffer = io.BytesIO()
            background = Image.new("RGB", image.size, "white")
            rgba = image.convert("RGBA")
            background.paste(rgba, mask=rgba.split()[3])
            background.save(buffer, format="JPEG", quality=92)
            export_data["jpeg"] = base64.b64encode(buffer.getvalue()).decode("ascii")
        return {"formats": list(export_data), "export_data": export_data, "timestamp": utc_now_iso()}

    # ------------------------------------------------------------------ #
    # Static metadata
    # ------------------------------------------------------------------ #

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        return [
            {"id": "pen", "name": "Pen", "description": "Freehand drawing tool", "capabilities": ["drawing"]},
            {"id": "eraser", "name": "Eraser", "description": "Remove strokes from the canvas", "capabilities": ["erasing"]},
            {"id": "text", "name": "Text", "description": "Add text to the canvas", "capabilities": ["text_input"]},
            {"id": "shapes", "name": "Shapes", "description": "Draw geometric shapes", "capabilities": ["rectangle", "circle", "line"]},
        ]

    async def get_recognition_types(self) -> List[Dict[str, Any]]:
        return [
            {"id": "equation_recognition", "name": "Equation Recognition", "requires_model": True},
            {"id": "handwriting_recognition", "name": "Handwriting Recognition", "requires_model": True},
            {"id": "shape_recognition", "name": "Shape Recognition", "requires_model": False},
        ]
