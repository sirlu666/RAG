from io import BytesIO

import numpy as np
from PIL import Image

from app.services.parsing import ocr, recognize


def fraction_image():
    image = np.full((130, 220, 3), 255, dtype=np.uint8)
    image[10:20, 10:40] = 0  # Chinese heading, separate from the formula
    image[45:52, 120:125] = 0  # numerator missed by the text detector
    image[62:64, 100:150] = 0  # fraction bar
    image[75:87, 100:145] = 0  # denominator
    lines = [ocr.OcrLine('求极限', .99, (10, 10, 40, 20)),
             ocr.OcrLine('f(x)', .9, (100, 48, 145, 65)),
             ocr.OcrLine('x2', .8, (100, 75, 145, 87))]
    return image, lines


def test_formula_crop_includes_undetected_numerator_and_denominator():
    image, lines = fraction_image()
    grouped = recognize._question_lines(image, lines)
    assert len(grouped) == 2
    assert grouped[0].text == '求极限'
    assert grouped[1].box == (100, 45, 150, 87)


def test_mixed_chinese_prose_is_not_sent_as_one_formula():
    image, lines = fraction_image()
    lines[1].text = '设函数 f(x)'
    grouped = recognize._question_lines(image, lines)
    assert len(grouped) == 3
    assert any(line.text == '设函数 f(x)' for line in grouped)


def test_recognizer_calls_formula_once_for_the_whole_fraction(monkeypatch):
    image, lines = fraction_image()
    raw = BytesIO()
    Image.fromarray(image).save(raw, format='PNG')
    monkeypatch.setattr(ocr, '_engine', lambda: lambda raw: ('fixture', None))
    monkeypatch.setattr(ocr, '_to_lines', lambda result: lines)
    seen = []
    def formula(crop):
        seen.append(crop.shape)
        return r'\frac{f(x)}{x^2}'
    monkeypatch.setattr(ocr, '_formula_engine', lambda: formula)
    text, latex, warnings = recognize._recognize_rapid(raw.getvalue())
    assert len(seen) == 1 and seen[0][0] >= 42
    assert text.startswith('求极限\n$$') and len(latex) == 1
    assert not warnings


def test_missing_formula_model_is_reported_instead_of_silent_text_fallback(monkeypatch):
    image, lines = fraction_image()
    raw = BytesIO()
    Image.fromarray(image).save(raw, format='PNG')
    monkeypatch.setattr(ocr, '_engine', lambda: lambda raw: ('fixture', None))
    monkeypatch.setattr(ocr, '_to_lines', lambda result: lines)
    monkeypatch.setattr(ocr, '_formula_engine', lambda: None)
    _, latex, warnings = recognize._recognize_rapid(raw.getvalue())
    assert not latex and any('公式模型不可用' in warning for warning in warnings)
