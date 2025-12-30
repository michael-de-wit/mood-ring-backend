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

# Global datetime range for API requests
# Heartrate API needs ISO 8601 datetime format (e.g. "2025-12-30T23:59:59Z")
# Session API needs date format (e.g. "2025-12-30")
oura_end_datetime = datetime.now(timezone.utc).isoformat() # current datetime in ISO format
oura_start_datetime = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat() # 1 day ago in ISO format
oura_end_date = datetime.now(timezone.utc).date().isoformat() # current date
oura_start_date = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat() # 1 day ago
print(f"{oura_end_datetime=}")
print(f"{oura_start_datetime=}")
print(f"{oura_end_date=}")
print(f"{oura_start_date=}")

# Store the latest HR data (shared across modules)
latest_hr_data = {
    "data": [],
    "last_updated": None,
    "count": 0
}

def get_hr_data(start_datetime=None, end_datetime=None): # Single GET request for heart rate data, i.e. not periodic
    """One-off GET heart rate data from Oura API."""
    headers = {"Authorization": f"Bearer {access_token}"}

    # Use global variables as defaults
    start_datetime = start_datetime or oura_start_datetime
    end_datetime = end_datetime or oura_end_datetime

    # GET heart rate data from Oura API
    hr_data = requests.get(
        "https://api.ouraring.com/v2/usercollection/heartrate",
        headers=headers,
        params={"start_datetime": start_datetime, "end_datetime": end_datetime}
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
    previous_hr_count = 0 # count of heart rate records from *previous* GET request

    while True:
        try:
            hr_data = get_hr_data()
            enhanced_hr_data = enhance_hr_data(hr_data)
            # print(f"{hr_data=}")
            current_hr_count = len(enhanced_hr_data) # count of heart rate records from *current* GET request
            hr_count_diff = current_hr_count - previous_hr_count # difference in number of heart rates records between the current and previous GET requests

            latest_hr_data["data"] = enhanced_hr_data
            latest_hr_data["last_updated"] = datetime.now().isoformat()
            latest_hr_data["count"] = current_hr_count
            # print(json.dumps(latest_hr_data, indent=2))

            print(f"Pulled {current_hr_count} heart rate records ({hr_count_diff:+d} records) at {latest_hr_data['last_updated']}. Updates every {interval_seconds} seconds.")

            # Notify if there's new heart rate data
            if notify_callback and hr_count_diff != 0:
                notify_callback({
                    "type": "heartrate_update", # front-end looks for this type to fetch HR data
                    "count": current_hr_count,
                    "count_diff": hr_count_diff,
                    "last_updated": latest_hr_data["last_updated"]
                })

            # Update combined biosensor data (this will notify if there are changes)
            update_combined_biosensor_data(hr_array=hr_data, notify_callback=notify_callback)

            # Update previous record count for next iteration
            previous_hr_count = current_hr_count

        except Exception as e:
            print(f"Error updating HR data: {e}")

        # Wait to re-call the function
        time.sleep(interval_seconds)

latest_session_data = {
    "data": [],
    "last_updated": None,
    "count": 0
}

# Store the latest combined biosensor data (shared across modules)
latest_combined_biosensor_data = {
    "data": [],
    "last_updated": None,
    "count": 0
}

def update_combined_biosensor_data(hr_array=None, notify_callback=None):
    """Update combined biosensor data and notify clients if there are changes.

    Args:
        hr_array: Pre-fetched heart rate data (if None, will fetch from API)
        notify_callback: Function to call for WebSocket notifications

    Returns:
        dict with 'count' and 'count_diff' keys
    """
    previous_count = latest_combined_biosensor_data["count"]

    # Get combined biosensor data
    combined_data = get_combined_biosensor_data(hr_array=hr_array)
    current_count = len(combined_data)
    count_diff = current_count - previous_count

    # Update global state
    latest_combined_biosensor_data["data"] = combined_data
    latest_combined_biosensor_data["last_updated"] = datetime.now().isoformat()
    latest_combined_biosensor_data["count"] = current_count

    print(f"Combined biosensor data: {current_count} total records ({count_diff:+d} records)")

    # Notify if there's new combined biosensor data
    if notify_callback and count_diff != 0:
        notify_callback({
            "type": "ouratimeseries_update",
            "count": current_count,
            "count_diff": count_diff,
            "last_updated": latest_combined_biosensor_data["last_updated"]
        })

    return {"count": current_count, "count_diff": count_diff}

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

def enhance_session_data(session_data_arrays: dict):
    """Convert session data arrays into BiosensorData format"""
    enhanced_session_data = []

    # Process heart_rate_array
    for record in session_data_arrays.get('heart_rate_array', []):
        biosensor_data = BiosensorData(
            timestamp=record.get("timestamp"),
            measurement_type="heartrate",
            measurement_value=record.get("heart_rate"),
            measurement_unit="bpm",
            sensor_mode="session",
            data_source="oura",
            device_source="oura_ring_4"
        )
        enhanced_session_data.append(biosensor_data.model_dump())

    # Process heart_rate_variability_array
    for record in session_data_arrays.get('heart_rate_variability_array', []):
        biosensor_data = BiosensorData(
            timestamp=record.get("timestamp"),
            measurement_type="heart_rate_variability",
            measurement_value=record.get("heart_rate_variability"),
            measurement_unit="ms",
            sensor_mode="session",
            data_source="oura",
            device_source="oura_ring_4"
        )
        enhanced_session_data.append(biosensor_data.model_dump())

    # Process motion_count_array
    for record in session_data_arrays.get('motion_count_array', []):
        biosensor_data = BiosensorData(
            timestamp=record.get("timestamp"),
            measurement_type="motion_count",
            measurement_value=record.get("motion_count"),
            measurement_unit="count",
            sensor_mode="session",
            data_source="oura",
            device_source="oura_ring_4"
        )
        enhanced_session_data.append(biosensor_data.model_dump())

    return enhanced_session_data

def combine_biosensor_data(enhanced_hr_array: list, enhanced_session_data: list):
    """Combine heart rate data and session data into a single unified array"""
    combined_data = []

    # Add all heart rate data
    combined_data.extend(enhanced_hr_array)

    # Add all session data
    combined_data.extend(enhanced_session_data)

    # Sort by timestamp
    combined_data.sort(key=lambda x: x.get('timestamp', ''))

    print(f"Combined {len(enhanced_hr_array)} HR records + {len(enhanced_session_data)} session records = {len(combined_data)} total records")

    return combined_data

def get_combined_biosensor_data(start_datetime=None, end_datetime=None, start_date=None, end_date=None, hr_array=None):
    """Get all combined biosensor data (HR + session data) for a date range

    Args:
        start_datetime: Start datetime for HR data retrieval (defaults to oura_start_datetime)
        end_datetime: End datetime for HR data retrieval (defaults to oura_end_datetime)
        start_date: Start date for session data retrieval (defaults to oura_start_date)
        end_date: End date for session data retrieval (defaults to oura_end_date)
        hr_array: Pre-fetched heart rate data (if None, will fetch from API)
    """
    # Use global variables as defaults
    start_datetime = start_datetime or oura_start_datetime
    end_datetime = end_datetime or oura_end_datetime
    start_date = start_date or oura_start_date
    end_date = end_date or oura_end_date

    # Get and enhance heart rate data (use provided data or fetch fresh)
    if hr_array is None:
        hr_array = get_hr_data(start_datetime, end_datetime)
    enhanced_hr_array = enhance_hr_data(hr_array)

    # Get and enhance session data
    session_array = get_initial_session_data(start_date, end_date)
    session_data_arrays = timestamp_session_data(session_array)
    enhanced_session_data = enhance_session_data(session_data_arrays)

    # Combine both datasets
    combined_data = combine_biosensor_data(enhanced_hr_array, enhanced_session_data)

    return combined_data

# Test the functions (commented out for production)
# hr_array = get_hr_data()
# enhanced_hr_array = enhance_hr_data(hr_array)
# enhanced_session_data = enhance_session_data(session_data_arrays)
# combined_biosensor_data = combine_biosensor_data(enhanced_hr_array, enhanced_session_data)
# print(f"Total biosensor records: {len(combined_biosensor_data)}")
# print(json.dumps(session_array_gl, indent=2))

