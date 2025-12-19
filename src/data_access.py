import requests
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Heart rate day start & end dates for GET from Oura API
hr_start_date = "2025-12-19"
hr_end_date = "2026-12-20"

# Step 3: Use the access token to make API calls
access_token = os.getenv("OURA_ACCESS_TOKEN")

# Store the latest HR data (shared across modules)
latest_hr_data = {
    "data": [],
    "last_updated": None,
    "count": 0
}

def get_hr_data(): # Single GET request for heart rate data, i.e. not periodic
    """GET heart rate data from Oura API."""
    headers = {"Authorization": f"Bearer {access_token}"}
    hr_data = requests.get(
        "https://api.ouraring.com/v2/usercollection/heartrate",
        headers=headers,
        params={"start_date": hr_start_date, "end_date": hr_end_date}
    )

    # Extract just the data from hr_data
    hr_array = hr_data.json().get('data', [])
    return hr_array

def update_hr_data_periodically(interval_seconds=60):
    """Background function that periodically updates the heart rate data"""
    while True:
        try:
            hr_data = get_hr_data()
            latest_hr_data["data"] = hr_data
            latest_hr_data["last_updated"] = datetime.now().isoformat()
            latest_hr_data["count"] = len(hr_data)
            print(f"Updated HR data: {len(hr_data)} records at {latest_hr_data['last_updated']}")
        except Exception as e:
            print(f"Error updating HR data: {e}")

        time.sleep(interval_seconds)