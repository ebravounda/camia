"""AI service: YOLOv8n object detection.

Singleton loader. First inference downloads the model (~6MB) automatically.
Runs on CPU. ~300-500ms per 640x480 frame on typical cloud CPU.
"""
from __future__ import annotations
import asyncio
import io
from pathlib import Path
from typing import List, Dict, Any, Optional

# Lazy load to avoid blocking startup
_model = None
_model_lock = asyncio.Lock()


def _load_sync():
    """Load YOLOv8n on demand. Called once."""
    from ultralytics import YOLO
    model_path = Path("/app/backend/yolov8n.pt")
    # Ultralytics auto-downloads if not present
    model = YOLO(str(model_path) if model_path.exists() else "yolov8n.pt")
    return model


async def get_model():
    global _model
    if _model is None:
        async with _model_lock:
            if _model is None:
                loop = asyncio.get_event_loop()
                _model = await loop.run_in_executor(None, _load_sync)
    return _model


def _infer_sync(model, jpeg_bytes: bytes, conf: float = 0.35) -> List[Dict[str, Any]]:
    """Run YOLO on raw JPEG bytes. Returns list of detections."""
    import numpy as np
    import cv2 as _cv2
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
    if img is None:
        return []
    results = model.predict(img, conf=conf, verbose=False, imgsz=480)
    detections: List[Dict[str, Any]] = []
    if not results:
        return detections
    r = results[0]
    names = r.names
    if r.boxes is None:
        return detections
    for box in r.boxes:
        cls_id = int(box.cls.item())
        confidence = float(box.conf.item())
        xyxy = box.xyxy.tolist()[0]  # [x1,y1,x2,y2]
        x1, y1, x2, y2 = [int(v) for v in xyxy]
        detections.append({
            "label": names.get(cls_id, str(cls_id)),
            "confidence": round(confidence, 3),
            "x": x1, "y": y1,
            "w": x2 - x1, "h": y2 - y1,
        })
    return detections


async def analyze_jpeg(jpeg_bytes: bytes, conf: float = 0.35) -> List[Dict[str, Any]]:
    model = await get_model()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _infer_sync, model, jpeg_bytes, conf)


# Spanish labels mapping for the most relevant COCO classes
LABEL_ES = {
    "person": "Persona", "bicycle": "Bicicleta", "car": "Coche", "motorcycle": "Moto",
    "airplane": "Avión", "bus": "Autobús", "train": "Tren", "truck": "Camión",
    "boat": "Barco", "traffic light": "Semáforo", "fire hydrant": "Hidrante",
    "stop sign": "Stop", "bench": "Banco", "bird": "Pájaro", "cat": "Gato",
    "dog": "Perro", "horse": "Caballo", "sheep": "Oveja", "cow": "Vaca",
    "backpack": "Mochila", "umbrella": "Paraguas", "handbag": "Bolso",
    "suitcase": "Maleta", "bottle": "Botella", "cup": "Taza", "chair": "Silla",
    "couch": "Sofá", "bed": "Cama", "tv": "TV", "laptop": "Portátil",
    "cell phone": "Móvil", "book": "Libro", "clock": "Reloj",
    "teddy bear": "Peluche",
}
