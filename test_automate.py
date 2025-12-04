#!/usr/bin/env python3
"""
Simplified Automated Test Script
- Only requires: test_id, image_path, expected_label
- Sends image to plant disease API
- Collects prediction + confidence
- Records pass/fail + latency
"""

import base64
import csv
import json
import time
from datetime import datetime
from pathlib import Path
import requests


# ====== CONFIG ======

TEST_CASES_CSV = "plant_ai_test_cases.csv"
RESULTS_CSV = "plant_ai_test_results.csv"

API_ENDPOINT = "https://www.plant.id/api_frontend/identify"
API_KEY = "REPLACE_WITH_KEY"                                # TODO: replace

# Column names in CSV
COL_TEST_ID = "test_id"
COL_IMAGE_PATH = "image_path"
COL_EXPECTED = "expected_label"


# ===== Helpers =====

def load_cases(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_api(image_path):
    img64 = encode_image(image_path)

    payload = {
        # For Plant.id, images can be base64 strings in a list
        "images": [img64],
        # These fields are aligned with the sample response you provided
        "classification_level": "all",
        "symptoms": True,
        "similar_images": True,
        "health": "all",
    }

    headers = {
        "Content-Type": "application/json",
        "Api-Key": API_KEY
    }

    r = requests.post(API_ENDPOINT, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    # ===== Adjust parsing to match Plant.id disease output =====
    # We expect: data["result"]["disease"]["suggestions"] to be a list
    result = data.get("result") or {}
    disease = (result.get("disease") or {})
    suggestions = disease.get("suggestions") or []
    if not suggestions:
        raise ValueError("No disease suggestions returned")

    # Choose the suggestion with highest probability
    best = max(suggestions, key=lambda s: s.get("probability", 0))
    label = best.get("name", "")
    prob = best.get("probability", 0)

    return label, prob, data


def normalize(s: str) -> str:
    return " ".join(s.lower().strip().split())


def matches(expected, predicted):
    e = normalize(expected)
    p = normalize(predicted)
    return e == p or e in p or p in e


def write_header(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "timestamp",
            "test_id",
            "image_path",
            "expected_label",
            "predicted_label",
            "confidence",
            "pass",
            "latency_sec",
            "error",
            "raw_response_snippet"
        ])


def append_result(path, row):
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            row["timestamp"],
            row["test_id"],
            row["image_path"],
            row["expected_label"],
            row["predicted_label"],
            row["confidence"],
            row["pass"],
            row["latency_sec"],
            row["error"],
            row["raw_response_snippet"]
        ])


# ===== Main =====

def main():
    cases = load_cases(TEST_CASES_CSV)
    write_header(RESULTS_CSV)

    for i, tc in enumerate(cases, start=1):
        test_id = tc[COL_TEST_ID]
        image_path = tc[COL_IMAGE_PATH]
        expected = tc[COL_EXPECTED]

        if not Path(image_path).is_file():
            print(f"[ERROR] Missing file: {image_path}")
            append_result(RESULTS_CSV, {
                "timestamp": datetime.now().isoformat(),
                "test_id": test_id,
                "image_path": image_path,
                "expected_label": expected,
                "predicted_label": "",
                "confidence": "",
                "pass": False,
                "latency_sec": 0,
                "error": "File not found",
                "raw_response_snippet": ""
            })
            continue

        print(f"\nRunning {test_id} - {image_path}")

        start = time.time()
        error = ""
        predicted = ""
        conf = 0
        passed = False
        snippet = ""

        try:
            predicted, conf, raw = call_api(image_path)
            passed = matches(expected, predicted)
            snippet = json.dumps(raw)[:150]

        except Exception as e:
            error = repr(e)

        latency = round(time.time() - start, 3)

        append_result(RESULTS_CSV, {
            "timestamp": datetime.now().isoformat(),
            "test_id": test_id,
            "image_path": image_path,
            "expected_label": expected,
            "predicted_label": predicted,
            "confidence": conf,
            "pass": passed,
            "latency_sec": latency,
            "error": error,
            "raw_response_snippet": snippet
        })

        print(f"Expected: {expected}")
        print(f"Predicted: {predicted} (conf={conf})")
        print(f"PASS: {passed}")
        print(f"Latency: {latency}s")


if __name__ == "__main__":
    main()
