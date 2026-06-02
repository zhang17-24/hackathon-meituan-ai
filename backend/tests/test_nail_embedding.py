import numpy as np
from PIL import Image

from packages.harness.deerflow.tools.nail import embedding


def test_sanitize_nail_bboxes_keeps_five_largest_valid_boxes():
    raw_bboxes = [
        {"x1": 0, "y1": 10, "x2": 8, "y2": 16},  # too small
        {"x1": 10, "y1": 10, "x2": 30, "y2": 30},
        {"x1": 35, "y1": 8, "x2": 55, "y2": 28},
        {"x1": 60, "y1": 9, "x2": 82, "y2": 31},
        {"x1": 85, "y1": 10, "x2": 108, "y2": 34},
        {"x1": 112, "y1": 12, "x2": 136, "y2": 38},
        {"x1": 140, "y1": 10, "x2": 166, "y2": 36},
    ]

    cleaned = embedding._sanitize_nail_bboxes(raw_bboxes, width=200, height=120)

    assert len(cleaned) == 5
    assert cleaned[0]["x1"] == 35
    assert cleaned[-1]["x1"] == 140


def test_aggregate_vectors_drops_clear_outlier():
    vectors = [
        np.array([1.0, 0.0, 0.0], dtype=np.float32),
        np.array([0.98, 0.02, 0.0], dtype=np.float32),
        np.array([0.97, 0.03, 0.0], dtype=np.float32),
        np.array([0.0, 1.0, 0.0], dtype=np.float32),
    ]

    aggregated = embedding._aggregate_vectors(vectors)

    assert aggregated is not None
    assert float(np.dot(aggregated, np.array([1.0, 0.0, 0.0], dtype=np.float32))) > 0.95
    assert float(np.dot(aggregated, np.array([0.0, 1.0, 0.0], dtype=np.float32))) < 0.2


def test_build_masked_focus_image_preserves_nails_and_subdues_background():
    image = Image.new("RGB", (40, 40), (0, 180, 0))
    for x in range(14, 26):
        for y in range(12, 28):
            image.putpixel((x, y), (220, 30, 30))

    result = embedding._build_masked_focus_image(image, [{"x1": 14, "y1": 12, "x2": 26, "y2": 28}])

    assert result.size == image.size
    assert result.getpixel((20, 20)) == image.getpixel((20, 20))
    assert result.getpixel((2, 2)) != image.getpixel((2, 2))
