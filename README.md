# Plant.id Test Automation

Automated test script for Plant.id API disease identification with visual dashboard.

## Quick Start

### 1. Setup

Install required Python package:
```bash
pip install requests
```

### 2. Configure API Key

Open `test_automate.py` and set your Plant.id API key:
```python
API_KEY = "your_api_key_here"
```

Get your API key from: https://web.plant.id/

### 3. Run Test Script

```bash
python test_automate.py
```

The script will:
- Read test cases from `plant_ai_test_cases.csv`
- Send images to Plant.id API
- Compare predictions with expected labels
- Generate results in `plant_ai_test_results.csv`

### 4. View Dashboard

**Option 1: Using Local Server (Recommended)**
```bash
python -m http.server 8000
```
Then open: `http://localhost:8000/dashboard.html`

**Option 2: Direct File**
- Double-click `dashboard.html` to open in browser
- Click "🔄 Refresh Results" button
- Select `plant_ai_test_results.csv` when prompted

## Test Cases

Edit `plant_ai_test_cases.csv` to add/modify test cases. Format:
```csv
test_id,crop,disease,image_path,expected_label,severity,area,focus,image_quality,lighting,visibility,weather_season
TC01,Tomato,Early Blight,images/tomato/image.jpg,Fungi,Moderate,Multi Spots,Sharp,Clear,Bright,FullLeaf,SuClear
```

## Output

Results are saved to `plant_ai_test_results.csv` with columns:
- Test details (ID, crop, disease, image path)
- Expected vs Predicted labels
- Confidence scores
- Pass/Fail status
- Test conditions (severity, lighting, quality, etc.)

## Dashboard Features

- Statistics overview (total, passed, failed, accuracy, avg confidence)
- Individual test cards with images
- Test conditions display
- Visual pass/fail indicators
