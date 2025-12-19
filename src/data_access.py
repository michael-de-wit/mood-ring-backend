import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Heart rate day start & end dates for GET from Oura API
hr_start_date = "2025-12-18"
hr_end_date = "2026-12-19"

# Step 3: Use the access token to make API calls
access_token = os.getenv("OURA_ACCESS_TOKEN")

def get_hr_data():
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