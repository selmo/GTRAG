"""
OCR 모듈: Azure Vision SDK 우선, 실패하면 로컬 Tesseract fall‑back.
"""
from pathlib import Path
from typing import List
import os, logging

# ---------- Azure Vision (권장) ----------
AZURE_KEY = os.getenv("AZURE_AI_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")

try:
    from azure.ai.vision import VisionServiceOptions, VisionSource, VisionAnalysisOptions, VisionAnalysisClient
    AZURE_AVAILABLE = AZURE_KEY and AZURE_ENDPOINT
except ImportError:
    AZURE_AVAILABLE = False

# ---------- Tesseract (백업) ----------
try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None


logger = logging.getLogger(__name__)


def _azure_ocr(image_path: str) -> str:
    """Azure AI Vision Read API"""
    service_options = VisionServiceOptions(AZURE_ENDPOINT, AZURE_KEY)
    client = VisionAnalysisClient(service_options)

    source = VisionSource(filename=image_path)
    analysis_options = VisionAnalysisOptions(features=["read"])
    result = client.analyze(source=source, analysis_options=analysis_options)

    if result.reason != "Analyzed":
        raise RuntimeError(f"Azure OCR failed: {result.error.message}")

    # 텍스트 블록 이어붙이기
    lines: List[str] = []
    for page in result.read_result.pages:
        for line in page.lines:
            lines.append(line.content)
    return "\n".join(lines)


def _tesseract_ocr(image_path: str, lang: str = "kor+eng") -> str:
    if not pytesseract:
        raise RuntimeError("pytesseract 미설치")
    img = Image.open(image_path)
    return pytesseract.image_to_string(img, lang=lang)


def extract_text(image_path: str, lang_hint: str = "auto") -> str:
    """
    이미지/스캔 PDF 한 페이지를 텍스트로 변환.
    lang_hint 예: 'kor', 'eng', 'jpn'…
    """
    if AZURE_AVAILABLE:
        try:
            return _azure_ocr(image_path)
        except Exception as e:
            logger.warning("Azure OCR 실패 → Tesseract fallback (%s)", e)

    return _tesseract_ocr(image_path, lang=lang_hint if lang_hint != "auto" else "kor+eng")
