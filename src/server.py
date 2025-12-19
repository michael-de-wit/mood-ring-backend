from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from data_access import get_hr_data, update_hr_data_periodically, latest_hr_data
import asyncio
from threading import Thread
from contextlib import asynccontextmanager

hr_update_frequency_sec = 60

@asynccontextmanager # context manager decorator; enables the before/after yield structure
async def lifespan(app: FastAPI): # lifespan function; before yield: upon app start-up; after yield: upon app shut-down
    """Manage application lifespan events."""
    # Startup: Start the background task to update HR data periodically
    thread = Thread(target=update_hr_data_periodically, args=(hr_update_frequency_sec,), daemon=True)
    thread.start()
    print(f"Started periodic HR data updates (every {hr_update_frequency_sec} seconds)")

    yield

    # Shutdown: Add any cleanup code here if needed
    print("Shutting down HR data updates...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/heartratetimeseries")
async def get_heart_rate_time_series_data():
    """Get the one-time fetched HR data."""
    hr_array = get_hr_data()
    return {"data": hr_array}


@app.get("/heartratetimeseries/live")
async def get_live_heart_rate_data():
    """Get the latest periodically-updated HR data."""
    return {"data": latest_hr_data["data"]}