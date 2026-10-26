"""
Reading images and scanned documents (Tanjim).

A photo has no text to extract, so two tools turn it into text that goes through the
normal pipeline (chunks, summary, embeddings, search):

* a captioning model (BLIP, runs locally) describes what the picture shows, so a dog,
  a meeting or a landscape photo can be found by describing it;
* OCR (Tesseract) reads any writing in the image (a slide, a receipt, a whiteboard)
  and every page of a scanned PDF.

Each tool is optional: if one is not installed or fails, the other still works.
"""
import io
import logging
import shutil
from dataclasses import dataclass
from functools import lru_cache

from app.ai_indexing.embeddings import model_lock

log = logging.getLogger(__name__)

CAPTION_MODEL = "Salesforce/blip-image-captioning-base"
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_PDF_PAGES = 30          # OCR is slow, so very long scans are read only up to this page
MIN_OCR_CHARS = 10          # fewer letters/digits than this is noise, not text
MAX_SIDE = 1600             # larger photos are shrunk before captioning/OCR


@dataclass(frozen=True)
class ImageReading:
    caption: str | None
    ocr_text: str

    def as_text(self) -> str:
        """The text stored for the file: the description first, then any writing found."""
        parts = []
        if self.caption:
            parts.append(f"This image shows {self.caption.rstrip('.')}.")
        if self.ocr_text:
            parts.append(f"Text found in the image:\n{self.ocr_text}")
        return "\n\n".join(parts)


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


@lru_cache(maxsize=1)
def _caption_model():
    from transformers import BlipForConditionalGeneration, BlipProcessor

    processor = BlipProcessor.from_pretrained(CAPTION_MODEL)
    model = BlipForConditionalGeneration.from_pretrained(CAPTION_MODEL)
    model.eval()
    return processor, model


def warm_up() -> None:
    """Load the captioning model now (called at startup). Failure is not fatal."""
    try:
        _caption_model()
    except Exception:
        log.warning("Image captioning model could not be loaded; photos will rely on OCR only", exc_info=True)


def _open(data: bytes):
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    return image


def is_sensible_caption(text: str) -> bool:
    """Captioning models ramble on pictures of text ("a page that reads ' ' ' ', ' '"):
    a real description is mostly letters, so drop anything that is mostly punctuation."""
    if not text:
        return False
    letters = sum(c.isalpha() or c == " " for c in text)
    return letters / len(text) >= 0.85 and len(text.split()) >= 2


def caption_image(image) -> str | None:
    try:
        processor, model = _caption_model()
        import torch

        with model_lock, torch.no_grad():  # one model call at a time, see embeddings.py
            inputs = processor(images=image, return_tensors="pt")
            output = model.generate(**inputs, max_new_tokens=40, num_beams=3)
        text = processor.decode(output[0], skip_special_tokens=True).strip()
        return text if is_sensible_caption(text) else None
    except Exception:
        log.warning("Captioning failed", exc_info=True)
        return None


def ocr_image(image) -> str:
    if not ocr_available():
        return ""
    try:
        import pytesseract
        from PIL import ImageOps

        gray = ImageOps.grayscale(image)
        if max(gray.size) < 1000:   # small text is read much better when enlarged
            gray = gray.resize((gray.width * 2, gray.height * 2))
        text = pytesseract.image_to_string(gray, timeout=60)
    except Exception:
        log.warning("OCR failed", exc_info=True)
        return ""
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return text if sum(c.isalnum() for c in text) >= MIN_OCR_CHARS else ""


def read_image(data: bytes) -> ImageReading:
    image = _open(data)
    return ImageReading(caption=caption_image(image), ocr_text=ocr_image(image))


def read_scanned_pdf(data: bytes) -> str:
    """OCR every page of a PDF that has no text layer."""
    if not ocr_available():
        return ""
    import pymupdf

    pages = []
    with pymupdf.open(stream=data, filetype="pdf") as document:
        for number, page in enumerate(document):
            if number >= MAX_PDF_PAGES:
                break
            png = page.get_pixmap(dpi=200).tobytes("png")
            text = ocr_image(_open(png))
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def read_file(data: bytes, extension: str) -> str:
    """Text for an image or scanned PDF ('' if nothing could be read)."""
    extension = extension.lower().lstrip(".")
    if extension in IMAGE_EXTENSIONS:
        return read_image(data).as_text()
    if extension == "pdf":
        return read_scanned_pdf(data)
    return ""
