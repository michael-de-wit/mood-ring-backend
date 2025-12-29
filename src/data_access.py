import requests
import json
import os
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

    # Heart rate start & end datetimes for Oura API GET
    hr_end_datetime = datetime.now(timezone.utc) # current time
    hr_start_datetime = hr_end_datetime - timedelta(days=1) # current time minus 1 day

     # Cast into string format for requests.get()
    hr_end_datetime_str = hr_end_datetime.isoformat()
    hr_start_datetime_str = hr_start_datetime.isoformat()

    # GET heart rate data from Oura API 
    hr_data = requests.get(
        "https://api.ouraring.com/v2/usercollection/heartrate",
        headers=headers,
        params={"start_datetime": hr_start_datetime_str, "end_datetime": hr_end_datetime_str}
    )

    # Extract just the heart rate data array from hr_data 'data' element
    hr_array = hr_data.json().get('data', [])
    print(f"{hr_array=}")
    return hr_array

def update_hr_data_periodically(interval_seconds=60, notify_callback=None):
    """Background function that periodically retrieves the most recent heart rate data"""
    previous_count = 0 # count of heart rate records from *previous* GET request

    while True:
        try:
            hr_data = get_hr_data()
            current_count = len(hr_data) # count of heart rate records from *current* GET request
            count_diff = current_count - previous_count # difference in number of heart rates records between the current and previous GET requests

            latest_hr_data["data"] = hr_data
            latest_hr_data["last_updated"] = datetime.now().isoformat()
            latest_hr_data["count"] = current_count

            print(f"Pulled {current_count} heart rate records ({count_diff:+d} records) at {latest_hr_data['last_updated']}. Updates every {interval_seconds} seconds.")

            # Create message for notification of websocket clients of the most recent GET request from Oura API
            if notify_callback:
                notify_callback({
                    "type": "heartrate_update", # front-end looks for this type to fetch data
                    "count": current_count,
                    "count_diff": count_diff,
                    "last_updated": latest_hr_data["last_updated"]
                })

            # Update previous heart rate record count for next iteration
            previous_count = current_count

        except Exception as e:
            print(f"Error updating HR data: {e}")

        # Wait to re-call the function
        time.sleep(interval_seconds)