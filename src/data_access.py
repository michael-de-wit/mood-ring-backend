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
    timestamp: str | None = None # e.g. "2025-12-29T05:38:58.000Z"
    measurement_type: str | None = None # e.g. "heartrate"
    measurement_value: int | float | str | None = None # e.g. 52 
    measurement_unit: str | None = None # e.g. "bpm"
    sensor_mode: str | None = None # e.g. "session"
    data_source: str | None = None # e.g. "oura"
    device_source: str | None = None # e.g. "oura_ring_4"

# Access token for Oura API
access_token = os.getenv("OURA_ACCESS_TOKEN")

# Global date range for API requests (date strings in 'YYYY-MM-DD' format)
oura_end_date = datetime.now(timezone.utc).date().isoformat() # current date
oura_start_date = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat() # 2 days ago
print(f"{oura_end_date=}")
print(f"{oura_start_date=}")

# Store the latest HR data (shared across modules)
latest_hr_data = {
    "data": [],
    "last_updated": None,
    "count": 0
}

def get_hr_data(start_date=None, end_date=None): # Single GET request for heart rate data, i.e. not periodic
    """One-off GET heart rate data from Oura API."""
    headers = {"Authorization": f"Bearer {access_token}"}

    # Use global variables as defaults
    start_date = start_date or oura_start_date
    end_date = end_date or oura_end_date

    # GET heart rate data from Oura API
    hr_data = requests.get(
        "https://api.ouraring.com/v2/usercollection/heartrate",
        headers=headers,
        params={"start_datetime": start_date, "end_datetime": end_date}
    )

    # Extract just the heart rate data array from hr_data 'data' element
    hr_array = hr_data.json().get('data', [])
    # print(f"{hr_array=}")
    return hr_array

def enhance_hr_data(hr_array):
    enhanced_hr_array = []
    for hr_record in hr_array:
        biosensor_data = BiosensorData(
            timestamp=hr_record.get("timestamp"),
            measurement_type="heartrate",
            measurement_value=hr_record.get("bpm"),
            measurement_unit="bpm",
            sensor_mode=hr_record.get("source"),
            data_source="oura",
            device_source="oura_ring_4"
        )
        enhanced_hr_array.append(biosensor_data.model_dump())
    return enhanced_hr_array

# hr_array = get_hr_data()
# enhanced_hr_array = enhance_hr_data(hr_array)

def update_hr_data_periodically(interval_seconds=60, notify_callback=None):
    """Background function that periodically retrieves the most recent heart rate data"""
    previous_count = 0 # count of heart rate records from *previous* GET request

    while True:
        try:
            hr_data = get_hr_data()
            enhanced_hr_data = enhance_hr_data(hr_data)
            # print(f"{hr_data=}")
            current_count = len(enhanced_hr_data) # count of heart rate records from *current* GET request
            count_diff = current_count - previous_count # difference in number of heart rates records between the current and previous GET requests

            latest_hr_data["data"] = enhanced_hr_data
            latest_hr_data["last_updated"] = datetime.now().isoformat()
            latest_hr_data["count"] = current_count
            # print(json.dumps(latest_hr_data, indent=2))

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

def get_initial_session_data(start_date=None, end_date=None):
    """One-off GET session data from Oura API"""
    headers = {"Authorization": f"Bearer {access_token}"}

    # Use global variables as defaults
    start_date = start_date or oura_start_date
    end_date = end_date or oura_end_date

    # GET session data from Oura API
    session_data = requests.get(
        "https://api.ouraring.com/v2/usercollection/session",
        headers=headers,
        params={"start_date": start_date, "end_date": end_date}
    )

    # Extract just the session 'data' element
    session_array = session_data.json().get('data', [])
    # print(f"{session_array=}")
    return session_array

session_array = get_initial_session_data(oura_start_date, oura_end_date)
# print(f"{session_array=}")

def timestamp_session_data(session_array: list):
    data_arrays = {
        'heart_rate_array': [],
        'heart_rate_variability_array': [],
        'motion_count_array': []
    }

    for session in session_array:
        # Looks for the e.g. heart_rate key in session_array
        # To save results in heart_rate_array of data_arrays
        for field_name, array_key in [
            ('heart_rate', 'heart_rate_array'),
            ('heart_rate_variability', 'heart_rate_variability_array'),
            ('motion_count', 'motion_count_array')
        ]:
            element = session.get(field_name)
            if not element:
                continue

            interval = float(element.get('interval', 0))
            items = element.get('items', [])
            timestamp_str = element.get('timestamp')

            # Assuming 'start' timestamp aligns with 2nd item, so subtract one interval to get base time
            # i.e. assumes that recording starts at t-10, first record at t-5, initial timestamp at t-0
            # assumes no record at the end timestampt
            ## checked against a 1 minute session; yielded 13 records; 1 @ t-5, 2 @ t-0, 3-12 @ t+5 to t+50, 13 @ t+55
            base_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')) - timedelta(seconds=interval)

            for i, value in enumerate(items):
                new_time = base_time + timedelta(seconds=i * interval)
                data_arrays[array_key].append({
                    field_name: value,
                    'timestamp': new_time.astimezone(timezone.utc).isoformat()
                })

    for key, array in data_arrays.items():
        print(f"Created {len(array)} {key} records")

    return data_arrays

session_data_arrays = timestamp_session_data(session_array)
print(f"{session_data_arrays=}")
# print(json.dumps(session_array_gl, indent=2))

