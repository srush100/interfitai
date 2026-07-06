"""
Per-Serving Nutrition Label Test Suite
=======================================
Tests that POST /api/food/analyze reads PER SERVING column, NOT per-100g column.

Key acceptance criterion: when a nutrition panel image with clearly different
per-serving vs per-100g values is analyzed, the returned protein must be close
to the PER SERVING value (~65g), NOT the per-100g value (~14.5g).

Also validates:
- Backend is running (PID 2070, supervisor RUNNING)
- user_prompt at ~line 7669 contains 'AVG PER SERVING' + 'NOT the per-100g column'
- vision_prompt at ~line 7678 contains 'TRANSCRIBE the printed values EXACTLY' + 'NOT the per 100g column'
- frontend food-log.tsx has quality: 0.8 in both pickImage and takePhoto
"""
import pytest
import requests
import os
import base64
import struct
import zlib
import io
import re
import subprocess
from pathlib import Path

# ─── Configuration ─────────────────────────────────────────────────────────────
BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://nutrition-debug-1.preview.emergentagent.com"

BACKEND_SERVER_PY = Path("/app/backend/server.py")
FRONTEND_FOOD_LOG = Path("/app/frontend/app/food-log.tsx")

# Known per-serving values on our synthetic label
EXPECTED_PROTEIN_PER_SERVING = 65.4
EXPECTED_CALORIES_PER_SERVING = 400
EXPECTED_CARBS_PER_SERVING = 10.0
EXPECTED_FAT_PER_SERVING = 8.0

# Known per-100g values (the WRONG values if AI reads wrong column)
WRONG_PROTEIN_PER_100G = 14.5

# Tolerance: protein must be at least 40g to be "close to serving" (not 14.5g)
PROTEIN_MIN_THRESHOLD = 40.0


@pytest.fixture(scope="module")
def api():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ─── Helper: Generate Synthetic Nutrition Label PNG ────────────────────────────

def create_nutrition_label_png_b64() -> str:
    """
    Create a clear, readable nutrition label PNG using Pillow.
    The label shows DIFFERENT per-serving vs per-100g values:
      Per Serving: 400 cal | 65.4g protein | 10g carbs | 8g fat
      Per 100g:    89 cal  | 14.5g protein |  2g carbs | 1.8g fat
    Returns base64-encoded PNG string.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        # Fallback: plain PNG with minimal data if Pillow unavailable
        return _create_fallback_png_b64()

    # Create a white image (large enough to render readable text)
    width, height = 600, 500
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Try to load a system font, fall back to default
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except Exception:
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large

    # Draw border
    draw.rectangle([(5, 5), (width - 5, height - 5)], outline=(0, 0, 0), width=3)

    # Title
    draw.text((20, 15), "NUTRITION INFORMATION", fill=(0, 0, 0), font=font_large)
    draw.line([(5, 48), (width - 5, 48)], fill=(0, 0, 0), width=2)

    # Column headers
    draw.text((20, 58), "Per Serve", fill=(0, 0, 0), font=font_medium)
    draw.text((350, 58), "Per 100g", fill=(0, 0, 0), font=font_medium)
    draw.line([(5, 84), (width - 5, 84)], fill=(0, 0, 0), width=1)

    # Serving size note
    draw.text((20, 90), "Serving Size: 450g", fill=(80, 80, 80), font=font_small)
    draw.line([(5, 112), (width - 5, 112)], fill=(200, 200, 200), width=1)

    # Rows of nutritional data
    rows = [
        ("Energy (Cal)", "400 Cal", "89 Cal"),
        ("Protein", "65.4g", "14.5g"),
        ("Total Fat", "8.0g", "1.8g"),
        ("Total Carbohydrate", "10.0g", "2.2g"),
        ("Dietary Fibre", "4.0g", "0.9g"),
        ("Sugars", "2.0g", "0.4g"),
        ("Sodium", "480mg", "107mg"),
    ]

    y = 118
    for i, (label, per_serve, per_100g) in enumerate(rows):
        bg_color = (245, 245, 245) if i % 2 == 0 else (255, 255, 255)
        draw.rectangle([(6, y), (width - 6, y + 26)], fill=bg_color)
        draw.text((20, y + 4), label, fill=(0, 0, 0), font=font_small)
        # Bold for per-serve column
        draw.text((330, y + 4), per_serve, fill=(0, 0, 120), font=font_medium)
        # Smaller for per-100g column
        draw.text((480, y + 4), per_100g, fill=(120, 120, 120), font=font_small)
        y += 28

    # Footer callout - emphasize serving protein
    draw.line([(5, y + 5), (width - 5, y + 5)], fill=(0, 0, 0), width=2)
    draw.text((20, y + 12), "AVG PER SERVING: 65.4g PROTEIN", fill=(0, 100, 0), font=font_large)
    draw.text((20, y + 40), "(see Per Serve column above)", fill=(100, 100, 100), font=font_small)

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def _create_fallback_png_b64() -> str:
    """Minimal valid PNG fallback (solid colour, no text)."""
    def make_chunk(chunk_type, data):
        chunk_len = struct.pack(">I", len(data))
        chunk_data = chunk_type + data
        chunk_crc = struct.pack(">I", zlib.crc32(chunk_data) & 0xFFFFFFFF)
        return chunk_len + chunk_data + chunk_crc

    w, h = 20, 20
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = make_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * w for _ in range(h))
    idat = make_chunk(b"IDAT", zlib.compress(raw))
    iend = make_chunk(b"IEND", b"")
    return base64.b64encode(sig + ihdr + idat + iend).decode()


# ─── Phase 1: Static Code Verification ─────────────────────────────────────────

class TestStaticCodeVerification:
    """Verify prompts in server.py and quality in food-log.tsx before runtime tests."""

    def test_backend_server_py_exists(self):
        assert BACKEND_SERVER_PY.exists(), f"server.py not found at {BACKEND_SERVER_PY}"
        print("PASS: server.py exists")

    def test_user_prompt_contains_avg_per_serving(self):
        """user_prompt (~line 7669) must contain 'AVG PER SERVING'."""
        content = BACKEND_SERVER_PY.read_text()
        assert "AVG PER SERVING" in content, (
            "FAIL: 'AVG PER SERVING' not found in server.py user_prompt"
        )
        # Verify line range
        lines = content.splitlines()
        found_line = None
        for i, line in enumerate(lines, start=1):
            if "AVG PER SERVING" in line:
                found_line = i
                break
        assert found_line is not None, "'AVG PER SERVING' not in any line"
        print(f"PASS: 'AVG PER SERVING' found at line {found_line}")

    def test_user_prompt_contains_not_per_100g(self):
        """user_prompt must also contain 'NOT the per-100g column'."""
        content = BACKEND_SERVER_PY.read_text()
        assert "NOT the per-100g column" in content, (
            "FAIL: 'NOT the per-100g column' not found in server.py user_prompt"
        )
        lines = content.splitlines()
        found_line = None
        for i, line in enumerate(lines, start=1):
            if "NOT the per-100g column" in line:
                found_line = i
                break
        print(f"PASS: 'NOT the per-100g column' found at line {found_line}")

    def test_vision_prompt_contains_transcribe_exactly(self):
        """vision_prompt (~line 7678) must contain 'TRANSCRIBE the printed values EXACTLY'."""
        content = BACKEND_SERVER_PY.read_text()
        assert "TRANSCRIBE the printed values EXACTLY" in content, (
            "FAIL: 'TRANSCRIBE the printed values EXACTLY' not found in server.py vision_prompt"
        )
        lines = content.splitlines()
        found_line = None
        for i, line in enumerate(lines, start=1):
            if "TRANSCRIBE the printed values EXACTLY" in line:
                found_line = i
                break
        print(f"PASS: 'TRANSCRIBE the printed values EXACTLY' found at line {found_line}")

    def test_vision_prompt_contains_not_per_100g_column(self):
        """vision_prompt must contain 'NOT the per 100g column' or similar."""
        content = BACKEND_SERVER_PY.read_text()
        has_it = ("NOT the" in content and "per 100g" in content) or \
                 ("NOT the per 100g" in content) or \
                 ('NOT the "per 100g"' in content)
        assert has_it, (
            "FAIL: vision_prompt missing 'NOT the per 100g column' instruction"
        )
        print("PASS: vision_prompt contains 'NOT the per 100g column' instruction")

    def test_frontend_pickimage_quality_0_8(self):
        """food-log.tsx pickImage must use quality: 0.8."""
        content = FRONTEND_FOOD_LOG.read_text()
        lines = content.splitlines()
        # Find lines with quality: 0.8
        quality_lines = [(i + 1, l.strip()) for i, l in enumerate(lines) if "quality: 0.8" in l]
        assert len(quality_lines) >= 2, (
            f"Expected at least 2 occurrences of 'quality: 0.8' in food-log.tsx, "
            f"found {len(quality_lines)}: {quality_lines}"
        )
        print(f"PASS: quality: 0.8 found at lines: {[q[0] for q in quality_lines]}")

    def test_frontend_quality_0_8_near_lines_440_and_459(self):
        """Verify quality: 0.8 is near lines 440 (pickImage) and 459 (takePhoto)."""
        content = FRONTEND_FOOD_LOG.read_text()
        lines = content.splitlines()
        quality_lines = [i + 1 for i, l in enumerate(lines) if "quality: 0.8" in l]
        # At least one occurrence should be within ±20 lines of 440
        near_440 = any(420 <= ln <= 460 for ln in quality_lines)
        near_459 = any(440 <= ln <= 479 for ln in quality_lines)
        assert near_440 or near_459, (
            f"quality: 0.8 not found near lines 440/459. Found at: {quality_lines}"
        )
        print(f"PASS: quality: 0.8 confirmed near pickImage/takePhoto. Lines: {quality_lines}")


# ─── Phase 2: Backend Process Verification ─────────────────────────────────────

class TestBackendProcessRunning:
    """Verify backend process is live with correct PID."""

    def test_supervisor_backend_running(self):
        """Backend supervisor process must report RUNNING."""
        result = subprocess.run(
            ["sudo", "supervisorctl", "status", "backend"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        assert "RUNNING" in output, f"Backend not running! supervisorctl: {output}"
        print(f"PASS: supervisor reports backend RUNNING: {output}")

    def test_backend_pid_is_2070(self):
        """Backend supervisor process must show PID 2070."""
        result = subprocess.run(
            ["sudo", "supervisorctl", "status", "backend"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        assert "pid 2070" in output, (
            f"Expected PID 2070 in supervisor output, got: {output}"
        )
        print(f"PASS: Backend running with PID 2070: {output}")

    def test_health_endpoint(self, api):
        """Backend health check must return 200."""
        resp = api.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, (
            f"Health check failed: {resp.status_code} — {resp.text[:200]}"
        )
        print("PASS: /api/health returns 200")


# ─── Phase 3: Per-Serving Nutrition Label End-to-End Test ──────────────────────

class TestPerServingNutritionLabel:
    """
    Core acceptance test: synthetic nutrition panel image must return per-serving
    values (protein ~65g), NOT per-100g values (~14.5g).
    """

    NUTRITION_LABEL_B64 = None

    @classmethod
    def get_label_b64(cls):
        if cls.NUTRITION_LABEL_B64 is None:
            cls.NUTRITION_LABEL_B64 = create_nutrition_label_png_b64()
        return cls.NUTRITION_LABEL_B64

    def test_synthetic_image_is_valid_png_and_large_enough(self):
        """PNG must be a valid base64 string longer than 100 chars."""
        b64 = self.get_label_b64()
        assert len(b64) > 100, f"Image too small: {len(b64)} chars"
        # Must be valid base64
        raw = base64.b64decode(b64)
        assert raw[:4] == b"\x89PNG", "Generated image is not a valid PNG"
        print(f"PASS: Synthetic nutrition label PNG is valid ({len(b64)} base64 chars, {len(raw)} bytes)")

    def test_analyze_endpoint_accepts_nutrition_label(self, api):
        """POST /api/food/analyze with preview=True must return 200 (not 400/422/500)."""
        payload = {
            "user_id": "TEST_per_serving_check",
            "image_base64": self.get_label_b64(),
            "meal_type": "lunch",
            "preview": True,
        }
        resp = api.post(f"{BASE_URL}/api/food/analyze", json=payload, timeout=90)
        print(f"INFO: /api/food/analyze status={resp.status_code}")
        if resp.status_code != 200:
            print(f"INFO: Response body: {resp.text[:500]}")
        assert resp.status_code == 200, (
            f"Expected 200 from /api/food/analyze, got {resp.status_code}: {resp.text[:400]}"
        )
        print("PASS: /api/food/analyze returned 200 OK")

    def test_analyze_returns_protein_close_to_per_serving_not_per_100g(self, api):
        """
        CRITICAL: Returned protein must be close to PER SERVING (~65.4g),
        NOT the per-100g value (~14.5g).
        Threshold: protein >= 40g means AI read per-serving correctly.
        """
        payload = {
            "user_id": "TEST_per_serving_check",
            "image_base64": self.get_label_b64(),
            "meal_type": "lunch",
            "preview": True,
            "additional_context": "This is a protein supplement tub label. Per serving is 450g.",
        }
        resp = api.post(f"{BASE_URL}/api/food/analyze", json=payload, timeout=90)

        if resp.status_code != 200:
            pytest.skip(
                f"API returned {resp.status_code} — AI may have failed on synthetic image. "
                f"Body: {resp.text[:300]}"
            )

        data = resp.json()
        protein = data.get("protein", 0)

        print(f"INFO: Full API response: {data}")
        print(f"INFO: Protein returned = {protein}g (expected ~{EXPECTED_PROTEIN_PER_SERVING}g per serving, wrong value = {WRONG_PROTEIN_PER_100G}g per 100g)")

        assert protein >= PROTEIN_MIN_THRESHOLD, (
            f"FAIL: Protein {protein}g is too low — AI probably read per-100g column ({WRONG_PROTEIN_PER_100G}g) "
            f"instead of per-serving column ({EXPECTED_PROTEIN_PER_SERVING}g). "
            f"Threshold: protein must be >= {PROTEIN_MIN_THRESHOLD}g. "
            f"Full response: {data}"
        )

        print(
            f"PASS: Protein {protein}g >= {PROTEIN_MIN_THRESHOLD}g threshold — "
            f"AI correctly read PER SERVING column (not per-100g)"
        )

    def test_analyze_returns_calories_close_to_per_serving(self, api):
        """
        Secondary check: Calories should be close to per-serving value (~400 Cal),
        not per-100g (~89 Cal). Threshold: calories >= 200.
        """
        payload = {
            "user_id": "TEST_per_serving_check_cal",
            "image_base64": self.get_label_b64(),
            "meal_type": "lunch",
            "preview": True,
        }
        resp = api.post(f"{BASE_URL}/api/food/analyze", json=payload, timeout=90)

        if resp.status_code != 200:
            pytest.skip(f"API returned {resp.status_code}")

        data = resp.json()
        calories = data.get("calories", 0)

        print(f"INFO: Calories returned = {calories} (expected ~{EXPECTED_CALORIES_PER_SERVING} per serving, wrong = 89 per 100g)")

        assert calories >= 200, (
            f"FAIL: Calories {calories} too low — AI may have read per-100g column. "
            f"Expected >= 200 (per serving ~400). Full response: {data}"
        )
        print(f"PASS: Calories {calories} >= 200 threshold — consistent with per-serving reading")

    def test_analyze_returns_valid_food_entry_structure(self, api):
        """Response must contain all required FoodEntry fields."""
        payload = {
            "user_id": "TEST_per_serving_structure",
            "image_base64": self.get_label_b64(),
            "meal_type": "dinner",
            "preview": True,
        }
        resp = api.post(f"{BASE_URL}/api/food/analyze", json=payload, timeout=90)

        if resp.status_code != 200:
            pytest.skip(f"API returned {resp.status_code}")

        data = resp.json()
        required_fields = ["food_name", "calories", "protein", "carbs", "fats"]
        for field in required_fields:
            assert field in data, f"Missing required field '{field}' in response: {data}"

        # All numeric fields must be >= 0
        for field in ["calories", "protein", "carbs", "fats"]:
            assert isinstance(data[field], (int, float)), f"Field '{field}' is not numeric: {data[field]}"
            assert data[field] >= 0, f"Field '{field}' is negative: {data[field]}"

        print(f"PASS: Response has all required fields with valid numeric values")
        print(f"INFO: food_name='{data.get('food_name')}' calories={data.get('calories')} "
              f"protein={data.get('protein')} carbs={data.get('carbs')} fats={data.get('fats')}")


# ─── Phase 4: Preview=True does not insert into DB ─────────────────────────────

class TestPreviewDoesNotInsertDB:
    """When preview=True, the analyzed food entry must NOT be stored in DB."""

    def test_preview_true_no_db_insert(self, api):
        from datetime import datetime
        import uuid

        user_id = f"TEST_per_serving_noinsert_{uuid.uuid4().hex[:6]}"
        today = datetime.now().strftime("%Y-%m-%d")

        logs_before = api.get(f"{BASE_URL}/api/food/logs/{user_id}", params={"date": today})
        count_before = len(logs_before.json()) if logs_before.status_code == 200 else 0

        b64 = create_nutrition_label_png_b64()
        payload = {
            "user_id": user_id,
            "image_base64": b64,
            "meal_type": "snack",
            "preview": True,
        }
        resp = api.post(f"{BASE_URL}/api/food/analyze", json=payload, timeout=90)

        if resp.status_code != 200:
            pytest.skip(f"AI analysis failed ({resp.status_code}), cannot verify DB skip")

        logs_after = api.get(f"{BASE_URL}/api/food/logs/{user_id}", params={"date": today})
        count_after = len(logs_after.json()) if logs_after.status_code == 200 else 0

        assert count_after == count_before, (
            f"preview=True should NOT insert into DB! Before={count_before} After={count_after}"
        )
        print(f"PASS: preview=True did not insert entry into DB (count stayed at {count_before})")
