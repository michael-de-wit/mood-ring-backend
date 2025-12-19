from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from data_access import get_hr_data

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/heartratetimeseries")
async def get_heart_rate_time_series_data():
    hr_array = get_hr_data()
    return {"data": hr_array}