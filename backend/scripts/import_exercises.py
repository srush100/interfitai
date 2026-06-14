#!/usr/bin/env python3
"""
One-time (re-runnable) script to import the full ExerciseDB catalog into MongoDB.
Run: python3 backend/scripts/import_exercises.py

Re-running is safe — uses upsert by exercisedb_id.
"""
import asyncio
import sys
import os

# Add backend dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import httpx
import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

MONGO_URL = os.getenv("MONGO_URL")
EXERCISEDB_API_KEY = os.getenv("EXERCISEDB_API_KEY")
EXERCISEDB_API_HOST = "exercisedb.p.rapidapi.com"
EXERCISEDB_API_BASE = "https://exercisedb.p.rapidapi.com"
BATCH_SIZE = 100
DELAY_BETWEEN_REQUESTS = 1.2  # seconds


async def run_import():
    if not EXERCISEDB_API_KEY:
        print("ERROR: EXERCISEDB_API_KEY not set in .env")
        return {"success": False, "error": "No API key"}

    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
    db = client[os.getenv('DB_NAME', 'interfitai')]

    headers = {
        "X-RapidAPI-Key": EXERCISEDB_API_KEY,
        "X-RapidAPI-Host": EXERCISEDB_API_HOST,
    }

    all_exercises = []
    offset = 0

    print("Fetching exercises from ExerciseDB...")
    async with httpx.AsyncClient(timeout=30.0) as http:
        while True:
            resp = await http.get(
                f"{EXERCISEDB_API_BASE}/exercises",
                headers=headers,
                params={"limit": BATCH_SIZE, "offset": offset},
            )
            if resp.status_code != 200:
                print(f"  API error at offset {offset}: HTTP {resp.status_code}")
                break

            batch = resp.json()
            if not batch:
                break

            all_exercises.extend(batch)
            print(f"  Fetched {len(all_exercises)} exercises (offset {offset})...")

            if len(batch) < BATCH_SIZE:
                break  # last page
            offset += BATCH_SIZE
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    if not all_exercises:
        print("No exercises fetched — aborting.")
        return {"success": False, "imported": 0}

    print(f"\nUpserting {len(all_exercises)} exercises into MongoDB...")
    upserted = 0
    for ex in all_exercises:
        exercise_id = ex.get("id", "")
        doc = {
            "exercisedb_id": exercise_id,
            "name": ex.get("name", "").strip(),
            "target": ex.get("target", "").strip(),
            "secondary_muscles": ex.get("secondaryMuscles", []),
            "body_part": ex.get("bodyPart", "").strip(),
            "equipment": ex.get("equipment", "").strip(),
            "gif_id": exercise_id,
            "instructions": ex.get("instructions", []),
        }
        await db.exercise_library.update_one(
            {"exercisedb_id": exercise_id},
            {"$set": doc},
            upsert=True,
        )
        upserted += 1

    # Create indexes for fast queries
    await db.exercise_library.create_index("target")
    await db.exercise_library.create_index("body_part")
    await db.exercise_library.create_index("equipment")
    await db.exercise_library.create_index([("name", 1)])

    # Print discovered target values so mapping can be verified
    targets = sorted(await db.exercise_library.distinct("target"))
    body_parts = sorted(await db.exercise_library.distinct("body_part"))
    total = await db.exercise_library.count_documents({})

    print(f"\nImport complete! {upserted} upserted, {total} total in collection.")
    print(f"\nUnique target values ({len(targets)}):\n  {targets}")
    print(f"\nUnique body_part values ({len(body_parts)}):\n  {body_parts}")

    client.close()
    return {"success": True, "imported": upserted, "total": total, "targets": targets}


if __name__ == "__main__":
    result = asyncio.run(run_import())
    sys.exit(0 if result.get("success") else 1)
