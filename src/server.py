from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from data_access import get_hr_data, update_hr_data_periodically, latest_hr_data
import asyncio
from threading import Thread

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Start the background task to update HR data periodically."""
    # Start background thread
    thread = Thread(target=update_hr_data_periodically, args=(60,), daemon=True)
    thread.start()
    print("Started periodic HR data updates (every 60 seconds)")


@app.get("/heartratetimeseries")
async def get_heart_rate_time_series_data():
    """Get the one-time fetched HR data."""
    hr_array = get_hr_data()
    return {"data": hr_array}


@app.get("/heartratetimeseries/live")
async def get_live_heart_rate_data():
    """Get the latest periodically-updated HR data."""
    return {"data": latest_hr_data["data"]}