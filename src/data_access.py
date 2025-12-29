import requests
import json
import os
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

class BiosensorData(BaseModel):
    timestamp: str
    measurement_type: str
    measurement_value: int | float | str
    measurement_unit: str
    sensor_mode: str
    data_source: str
    device_source: str

# Access token for Oura API
access_token = os.getenv("OURA_ACCESS_TOKEN")

# GET OURA HEART RATE DATA
# Store the latest HR data (shared across modules)
latest_hr_data = {
    "data": [],
    "last_updated": None,
    "count": 0
}

def get_hr_data(): # Single GET request for heart rate data, i.e. not periodic
    """One-off GET heart rate data from Oura API."""
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
    return hr_array

def enhance_hr_data(hr_array):
    enhanced_hr_array = hr_array
    return enhanced_hr_array

hr_array = get_hr_data()
enhanced_hr_array = enhance_hr_data(hr_array)
print(f"{enhanced_hr_array=}")

def update_hr_data_periodically(interval_seconds=60, notify_callback=None):
    """Background function that periodically retrieves the most recent heart rate data"""
    previous_count = 0 # count of heart rate records from *previous* GET request

    while True:
        try:
            hr_data = get_hr_data()
            # print(f"{hr_data=}")
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

latest_session_data = {
    "data": [],
    "last_updated": None,
    "count": 0
}

def get_initial_session_data():
    """One-off GET session data from Oura API"""
    headers = {"Authorization": f"Bearer {access_token}"}

    # Session start & end datetimes for Oura API GET request
    session_end_datetime = datetime.now(timezone.utc) # current time
    session_start_datetime = session_end_datetime - timedelta(days=1) # current time minus 1 day

     # Cast into string format for requests.get()
    session_end_datetime_str = session_end_datetime.isoformat()
    session_start_datetime_str = session_start_datetime.isoformat()

    # GET session data from Oura API 
    session_data = requests.get(
        "https://api.ouraring.com/v2/usercollection/session",
        headers=headers,
        params={"start_datetime": session_start_datetime_str, "end_datetime": session_end_datetime_str}
    )

    # Extract just the heart rate data array from hr_data 'data' element
    session_array = session_data.json().get('data', [])
    # print(f"{session_array=}")
    return session_array

session_array_gl = get_initial_session_data()
# print(json.dumps(session_array_gl, indent=2))

# timestamp: "2025-12-29T05:38:58.000Z"
# measurement_type: "heartrate"
# measurement_value: 52
# measurement_unit: "bpm"
# sensor_mode: "session"
# data_source: "oura"
# device_source: "oura_ring_4"