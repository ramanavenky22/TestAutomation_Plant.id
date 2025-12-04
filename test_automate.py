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

API_ENDPOINT = "https://plant.id/api/v3/health_assessment"
API_KEY = "kvL33dBNCNVJRStT3yoabtSeHZFv6aNzh2CDqOPNjklLVf8i2U"                                

# Column names in CSV
COL_TEST_ID = "test_id"
COL_CROP = "crop"
COL_DISEASE = "disease"
COL_IMAGE_PATH = "image_path"
COL_EXPECTED = "expected_label"
# Metadata columns (optional - for documentation and analysis)
COL_SEVERITY = "severity"
COL_AREA = "area"
COL_FOCUS = "focus"
COL_IMAGE_QUALITY = "image_quality"
COL_LIGHTING = "lighting"
COL_VISIBILITY = "visibility"
COL_WEATHER_SEASON = "weather_season"


# ===== Helpers =====

def load_cases(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=','))


def encode_image(image_path):
    """Encode image as base64 data URL format"""
    path = Path(image_path)
    ext = path.suffix.lower()
    
    # Determine MIME type from extension
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    mime_type = mime_types.get(ext, 'image/jpeg')
    
    with open(image_path, "rb") as f:
        img64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{img64}"


def call_api(image_path):
    """Call Plant.id health assessment API"""
    img_data_url = encode_image(image_path)

    payload = {
        "images": [img_data_url]
    }

    headers = {
        "Content-Type": "application/json",
        "Api-Key": API_KEY
    }

    print(f"\n{'='*80}")
    print(f"[API Request]")
    print(f"URL: {API_ENDPOINT}")
    print(f"Image: {image_path}")
    print(f"Payload: {{'images': ['data:image/...;base64,<encoded>']}}")
    print(f"Headers: {{'Content-Type': 'application/json', 'Api-Key': '***'}}")
    
    r = requests.post(API_ENDPOINT, json=payload, headers=headers, timeout=60)
    
    # Handle rate limiting (429) with retry
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", 60))
        print(f"[Rate Limit] 429 Too Many Requests. Waiting {retry_after} seconds before retry...")
        time.sleep(retry_after)
        r = requests.post(API_ENDPOINT, json=payload, headers=headers, timeout=60)
    
    # Log error response if not successful
    if not r.ok:
        print(f"[Error Response] Status: {r.status_code}")
        try:
            error_data = r.json()
            print(f"[Error Body]: {json.dumps(error_data, indent=2)}")
        except:
            print(f"[Error Text]: {r.text[:500]}")
    
    r.raise_for_status()
    data = r.json()
    
    print(f"[API Response]")
    print(f"Status Code: {r.status_code}")
    print(f"Response Headers: {dict(r.headers)}")
    
    # ===== Check if image is a plant =====
    result = data.get("result") or {}
    is_plant = result.get("is_plant", {})
    is_plant_binary = is_plant.get("binary", True)
    is_plant_prob = is_plant.get("probability", 1.0)
    
    print(f"\n[Plant Detection]")
    print(f"  Is Plant: {is_plant_binary} (probability: {is_plant_prob*100:.2f}%)")
    
    # If not a plant, return special indicator
    if not is_plant_binary or is_plant_prob < 0.5:
        print(f"[WARNING] Image does not appear to be a plant!")
        return "NOT_A_PLANT", 0.0, data, []
    
    # ===== Parse disease suggestions from response =====
    # Based on the sample response structure: data["result"]["disease"]["suggestions"]
    disease = (result.get("disease") or {})
    suggestions = disease.get("suggestions") or []
    
    if not suggestions:
        print(f"[WARNING] No disease suggestions found in response.")
        print(f"Available keys in result: {list(result.keys())}")
        print(f"Full response structure:")
        print(json.dumps(data, indent=2))
        raise ValueError("No disease suggestions returned")

    # Print all disease suggestions with probabilities
    print(f"\n[Disease Suggestions] (Total: {len(suggestions)})")
    for idx, sug in enumerate(suggestions, 1):
        name = sug.get("name", "N/A")
        prob = sug.get("probability", 0)
        prob_pct = prob * 100
        print(f"  {idx}. {name:<40} Probability: {prob_pct:.2f}% ({prob:.4f})")
    
    # Choose the suggestion with highest probability
    best = max(suggestions, key=lambda s: s.get("probability", 0))
    label = best.get("name", "")
    prob = best.get("probability", 0)
    
    print(f"\n[Top Prediction]")
    print(f"  Label: {label}")
    print(f"  Probability: {prob * 100:.2f}% ({prob:.4f})")

    # Return all suggestion names for matching
    all_labels = [s.get("name", "") for s in suggestions]
    
    print(f"[All Labels for Matching]: {all_labels}")
    print(f"{'='*80}\n")
    
    return label, prob, data, all_labels


def normalize(s: str) -> str:
    return " ".join(s.lower().strip().split())


def matches(expected, predicted, all_suggestions=None):
    """Check if expected matches predicted or appears in suggestions"""
    # Special case: if predicted is NOT_A_PLANT, only match if expected is also NOT_A_PLANT
    if predicted == "NOT_A_PLANT":
        return expected.lower() == "not_a_plant" or expected.lower() == "not a plant"
    
    e = normalize(expected)
    p = normalize(predicted)
    
    # Check exact match with top prediction
    if e == p or e in p or p in e:
        return True
    
    # Check if expected appears in any of the suggestions
    if all_suggestions:
        for suggestion_label in all_suggestions:
            s = normalize(suggestion_label)
            if e == s or e in s or s in e:
                return True
    
    return False


def write_header(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "timestamp",
            "test_id",
            "crop",
            "disease",
            "image_path",
            "expected_label",
            "predicted_label",
            "confidence",
            "pass",
            "severity",
            "area",
            "focus",
            "image_quality",
            "lighting",
            "visibility",
            "weather_season"
        ])


def append_result(path, row):
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            row["timestamp"],
            row["test_id"],
            row.get("crop", ""),
            row.get("disease", ""),
            row["image_path"],
            row["expected_label"],
            row["predicted_label"],
            row["confidence"],
            row["pass"],
            row.get("severity", ""),
            row.get("area", ""),
            row.get("focus", ""),
            row.get("image_quality", ""),
            row.get("lighting", ""),
            row.get("visibility", ""),
            row.get("weather_season", "")
        ])


# ===== Main =====

def main():
    cases = load_cases(TEST_CASES_CSV)
    write_header(RESULTS_CSV)

    for i, tc in enumerate(cases, start=1):
        test_id = tc.get(COL_TEST_ID, f"TC{i:02d}")
        crop = tc.get(COL_CROP, "")
        disease = tc.get(COL_DISEASE, "")
        image_path = tc[COL_IMAGE_PATH]
        expected = tc.get(COL_EXPECTED, "")
        
        # Get metadata (optional columns)
        severity = tc.get(COL_SEVERITY, "")
        area = tc.get(COL_AREA, "")
        focus = tc.get(COL_FOCUS, "")
        image_quality = tc.get(COL_IMAGE_QUALITY, "")
        lighting = tc.get(COL_LIGHTING, "")
        visibility = tc.get(COL_VISIBILITY, "")
        weather_season = tc.get(COL_WEATHER_SEASON, "")
        
        # If expected_label is not provided, construct it from crop + disease
        if not expected and crop and disease:
            expected = f"{crop.lower()} {disease.lower()}"

        if not Path(image_path).is_file():
            print(f"[ERROR] Missing file: {image_path}")
            append_result(RESULTS_CSV, {
                "timestamp": datetime.now().isoformat(),
                "test_id": test_id,
                "crop": crop,
                "disease": disease,
                "image_path": image_path,
                "expected_label": expected,
                "predicted_label": "",
                "confidence": "",
                "pass": False,
                "severity": severity,
                "area": area,
                "focus": focus,
                "image_quality": image_quality,
                "lighting": lighting,
                "visibility": visibility,
                "weather_season": weather_season
            })
            continue

        print(f"\nRunning {test_id} - {crop} {disease} - {image_path}")
        
        # Display test conditions
        if severity or area or focus or image_quality or lighting or visibility or weather_season:
            print(f"[Test Conditions]")
            if severity: print(f"  Severity: {severity}")
            if area: print(f"  Area: {area}")
            if focus: print(f"  Focus: {focus}")
            if image_quality: print(f"  Image Quality: {image_quality}")
            if lighting: print(f"  Lighting: {lighting}")
            if visibility: print(f"  Visibility: {visibility}")
            if weather_season: print(f"  Weather/Season: {weather_season}")

        start = time.time()
        error = ""
        predicted = ""
        conf = 0
        passed = False
        raw = None
        all_labels = []

        try:
            predicted, conf, raw, all_labels = call_api(image_path)
            
            # Detailed matching analysis
            print(f"\n[Test Case Details]")
            print(f"  Test ID: {test_id}")
            print(f"  Crop: {crop}")
            print(f"  Disease: {disease}")
            print(f"  Image: {image_path}")
            print(f"  Expected Label: '{expected}'")
            print(f"  Top Predicted: '{predicted}' (confidence: {conf*100:.2f}%)")
            
            # Check matching
            print(f"\n[Matching Analysis]")
            e_norm = normalize(expected)
            p_norm = normalize(predicted)
            print(f"  Normalized Expected: '{e_norm}'")
            print(f"  Normalized Predicted: '{p_norm}'")
            
            # Check top prediction match
            top_match = (e_norm == p_norm or e_norm in p_norm or p_norm in e_norm)
            print(f"  Top Prediction Match: {top_match}")
            
            # Check all suggestions
            found_in_suggestions = False
            matching_suggestions = []
            for idx, suggestion_label in enumerate(all_labels, 1):
                s_norm = normalize(suggestion_label)
                if e_norm == s_norm or e_norm in s_norm or s_norm in e_norm:
                    found_in_suggestions = True
                    matching_suggestions.append((idx, suggestion_label))
            
            if matching_suggestions:
                print(f"  Found in Suggestions: YES")
                for idx, label in matching_suggestions:
                    print(f"    - Position {idx}: '{label}'")
            else:
                print(f"  Found in Suggestions: NO")
                print(f"  All suggestions checked: {all_labels}")
            
            passed = matches(expected, predicted, all_labels)
            print(f"\n[Final Result]")
            print(f"  PASS: {passed}")
            
            # Add a small delay between API calls to avoid rate limits (1-2 seconds)
            if i < len(cases):
                time.sleep(1.5)

        except Exception as e:
            error = repr(e)
            print(f"\n[ERROR] {error}")
            print(f"  Test ID: {test_id}")
            print(f"  Image: {image_path}")
            print(f"  Expected: {expected}")
            if raw is not None:
                print(f"\n[API Response on Error]:")
                print(json.dumps(raw, indent=2))

        latency = round(time.time() - start, 3)
        
        print(f"\n[Test Summary]")
        print(f"  Expected: {expected}")
        print(f"  Predicted: {predicted} (conf={conf*100:.2f}%)")
        print(f"  PASS: {passed}")
        print(f"  Latency: {latency}s")
        print(f"{'='*80}\n")

        append_result(RESULTS_CSV, {
            "timestamp": datetime.now().isoformat(),
            "test_id": test_id,
            "crop": crop,
            "disease": disease,
            "image_path": image_path,
            "expected_label": expected,
            "predicted_label": predicted,
            "confidence": conf,
            "pass": passed,
            "severity": severity,
            "area": area,
            "focus": focus,
            "image_quality": image_quality,
            "lighting": lighting,
            "visibility": visibility,
            "weather_season": weather_season
        })


if __name__ == "__main__":
    main()
