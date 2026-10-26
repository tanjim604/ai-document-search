import io

import pytest
from PIL import Image, ImageDraw

from app import vision
from app.vision import ImageReading


def test_text_puts_the_description_first_then_the_writing():
    reading = ImageReading(caption="a dog on a couch", ocr_text="Beware of dog")
    assert reading.as_text() == "This image shows a dog on a couch.\n\nText found in the image:\nBeware of dog"


def test_caption_only_and_ocr_only():
    assert ImageReading("a cat", "").as_text() == "This image shows a cat."
    assert ImageReading(None, "Invoice 42").as_text() == "Text found in the image:\nInvoice 42"
    assert ImageReading(None, "").as_text() == ""


def test_read_file_ignores_other_types():
    assert vision.read_file(b"hello", "txt") == ""


def test_corrupt_image_raises_so_the_pipeline_can_flag_it():
    with pytest.raises(Exception):
        vision.read_image(b"not an image")


@pytest.mark.skipif(not vision.ocr_available(), reason="Tesseract is not installed")
def test_ocr_reads_text_drawn_in_an_image():
    image = Image.new("RGB", (900, 200), "white")
    ImageDraw.Draw(image).text((30, 80), "Quarterly budget review meeting", fill="black", font_size=48)
    text = vision.ocr_image(image)
    assert "budget" in text.lower() and "meeting" in text.lower()


def test_noise_is_not_treated_as_text(monkeypatch):
    class FakeTesseract:
        @staticmethod
        def image_to_string(image, timeout):
            return "  ~ . \n |"

    monkeypatch.setattr(vision, "ocr_available", lambda: True)
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", FakeTesseract)
    assert vision.ocr_image(Image.new("RGB", (50, 50))) == ""


@pytest.mark.parametrize("caption, ok", [
    ("a small dog standing in the grass", True),
    ("two cats sleeping on a couch", True),
    ("a white background with a black and white text that reads, ' ' ' ', ' ', ' ', ', ', ',", False),
    ("", False),
    ("dog", False),
])
def test_rambling_captions_are_dropped(caption, ok):
    assert vision.is_sensible_caption(caption) is ok
