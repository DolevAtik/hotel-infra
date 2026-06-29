#!/usr/bin/env python3
"""Phase 1 smoke test: verify the backend works against a real MongoDB.

Flow:
  1. Wait for the backend /health endpoint.
  2. Seed a hotel directly into MongoDB (there is no create-hotel endpoint).
  3. GET /hotels and pick the seeded hotel's id.
  4. POST /reservations (create) and assert 201.
  5. GET /reservations/<id> (lookup) and assert it matches.
  6. DELETE /reservations/<id> (cancel) and assert 200.
  7. GET /reservations/<id> again and assert 404.

Run from the hotel-infra directory after `docker compose up -d --build`.
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://localhost:5000"
MONGO_USER = "admin"
MONGO_PASS = "admin123"
MONGO_DB = "hotel"

PASS = "[PASS]"
FAIL = "[FAIL]"


def request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode() or "null"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode() or "null"
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def check(label, condition, detail=""):
    mark = PASS if condition else FAIL
    print(f"  {mark} {label}" + (f" -> {detail}" if detail else ""))
    if not condition:
        raise SystemExit(f"\nSmoke test FAILED at: {label}")


def wait_for_health(timeout=90):
    print(f"Waiting for backend at {BASE_URL}/health ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, body = request("GET", "/health")
            if status == 200 and body.get("status") == "ok":
                print(f"  {PASS} backend healthy")
                return
        except urllib.error.URLError:
            pass
        time.sleep(2)
    raise SystemExit(f"{FAIL} backend did not become healthy within {timeout}s")


def seed_hotel():
    print("Seeding a hotel into MongoDB via mongosh ...")
    js = (
        'db.hotels.insertOne({'
        'name:"Grand Smoke Hotel",'
        'description:"Seeded by the phase 1 smoke test",'
        'location:"Tel Aviv",'
        'price_per_night:450'
        '})'
    )
    cmd = [
        "docker", "compose", "exec", "-T", "mongodb",
        "mongosh", "-u", MONGO_USER, "-p", MONGO_PASS,
        "--authenticationDatabase", "admin",
        MONGO_DB, "--quiet", "--eval", js,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(f"{FAIL} failed to seed hotel")
    print(f"  {PASS} hotel seeded")


def main():
    print("=" * 60)
    print("Phase 1 Smoke Test — Backend + real MongoDB")
    print("=" * 60)

    wait_for_health()
    seed_hotel()

    # Step: list hotels and grab a real hotel_id
    print("GET /hotels")
    status, hotels = request("GET", "/hotels")
    check("status 200", status == 200, str(status))
    check("at least one hotel exists", isinstance(hotels, list) and len(hotels) > 0,
          f"{len(hotels) if isinstance(hotels, list) else '?'} hotels")
    hotel_id = hotels[-1]["hotel_id"]
    print(f"      using hotel_id = {hotel_id}")

    # Step: create reservation
    print("POST /reservations")
    payload = {
        "full_name": "Smoke Tester",
        "email": "smoke@example.com",
        "check_in_date": "2026-07-01",
        "check_out_date": "2026-07-05",
        "hotel_id": hotel_id,
    }
    status, created = request("POST", "/reservations", payload)
    check("status 201", status == 201, str(status))
    check("returns reservation_id",
          isinstance(created, dict) and "reservation" in created
          and "reservation_id" in created["reservation"])
    reservation_id = created["reservation"]["reservation_id"]
    print(f"      created reservation_id = {reservation_id}")

    # Step: lookup
    print(f"GET /reservations/{reservation_id}")
    status, found = request("GET", f"/reservations/{reservation_id}")
    check("status 200", status == 200, str(status))
    check("email matches", found.get("email") == "smoke@example.com",
          found.get("email"))
    check("hotel_id matches", found.get("hotel_id") == hotel_id)

    # Step: invalid create is rejected (business-rule validation)
    print("POST /reservations (invalid: checkout before checkin)")
    bad = dict(payload, check_in_date="2026-07-05", check_out_date="2026-07-01")
    status, _ = request("POST", "/reservations", bad)
    check("status 400", status == 400, str(status))

    # Step: cancel
    print(f"DELETE /reservations/{reservation_id}")
    status, cancelled = request("DELETE", f"/reservations/{reservation_id}")
    check("status 200", status == 200, str(status))
    check("cancellation confirmed",
          isinstance(cancelled, dict) and "message" in cancelled)

    # Step: confirm gone
    print(f"GET /reservations/{reservation_id} (should be gone)")
    status, _ = request("GET", f"/reservations/{reservation_id}")
    check("status 404", status == 404, str(status))

    print("=" * 60)
    print("ALL CHECKS PASSED — Phase 1 is closed. ")
    print("=" * 60)


if __name__ == "__main__":
    main()
