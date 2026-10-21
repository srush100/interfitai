"""Run the user's REAL photos through the live /api/food/analyze (real AI
vision read) with each description, and compare what the app would log with
the numbers worked out by hand from the printed label.

    python scripts/snap_real_photos.py yoghurt /tmp/snap/yoghurt.jpg
    python scripts/snap_real_photos.py plate /tmp/snap/eggs_plate.jpg "" "4 eggs and 3 pieces of sourdough"

Results are written to /app/memory/snap_real_photos_<name>.json."""
import base64
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
API = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") + "/api"
USER_ID = "2663e0c4-d8b9-4feb-b42a-8b055631ea25"  # sdk57tester (premium access)

# The user's tub: 5 servings × 180g = 900g; per 100g 56 Cal · 9.1P · 4.3C · 0.1F
YOGHURT_PER_100G = {"calories": 56, "protein": 9.1, "carbs": 4.3, "fats": 0.1}
YOGHURT_CASES = [("", 180, "1 serving"), ("200g", 200, "200g"), ("half", 90, "half a serving"),
                 ("1/2 serving", 90, "half a serving"), ("about 300g", 300, "300g"),
                 ("the whole pack", 900, "the whole 900g tub"), ("no dressing", 180, "1 serving"),
                 ("1 cup", 245, "1 cup of yoghurt (245g)")]


def analyze(image_b64: str, text: str) -> dict:
    t = time.time()
    r = requests.post(f"{API}/food/analyze", timeout=180, json={
        "user_id": USER_ID, "image_base64": image_b64, "meal_type": "snack",
        "additional_context": text or None, "quantity": 1, "preview": True})
    body = r.json()
    return {"status": r.status_code, "seconds": round(time.time() - t, 1), **(body if r.ok else {"detail": body.get("detail")})}


def main():
    name, path, *texts = sys.argv[1:]
    image_b64 = base64.b64encode(open(path, "rb").read()).decode()
    rows = []
    if name == "yoghurt":
        for text, grams, meaning in YOGHURT_CASES:
            b = analyze(image_b64, text)
            exp = {k: round(v * grams / 100, 1) for k, v in YOGHURT_PER_100G.items()}
            exp["calories"] = round(exp["calories"])
            rows.append({"description": text, "expected": {"grams": grams, "meaning": meaning, **exp},
                         "logged": {k: b.get(k) for k in ("status", "food_name", "serving_size", "portion_g_applied",
                                                           "calories", "protein", "carbs", "fats", "summary",
                                                           "label_per_100g", "label_serving_size_g",
                                                           "label_package_g", "portion_source", "detail",
                                                           "seconds")}})
            print(json.dumps(rows[-1]), flush=True)
    else:
        for text in texts or [""]:
            b = analyze(image_b64, text)
            rows.append({"description": text, "logged": {k: b.get(k) for k in (
                "status", "food_name", "portion_g_applied", "calories", "protein", "carbs", "fats",
                "items", "portion_debug", "detail", "seconds")}})
            print(json.dumps(rows[-1]), flush=True)
    out = f"/app/memory/snap_real_photos_{name}.json"
    json.dump(rows, open(out, "w"), indent=1)
    print("written", out)


if __name__ == "__main__":
    main()
