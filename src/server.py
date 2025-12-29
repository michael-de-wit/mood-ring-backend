from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from threading import Thread
from contextlib import asynccontextmanager
from pydantic import BaseModel # data type validation
import os
from dotenv import load_dotenv
from typing import List
import asyncio

# import data_access.py functions
from data_access import get_hr_data, update_hr_data_periodically, latest_hr_data

load_dotenv()

hr_update_frequency_sec = 20 # polling frequency of Oura API; in seconds; assumes webhook not available

@asynccontextmanager # context manager decorator; enables the before/after yield structure
async def lifespan(app: FastAPI): # lifespan function; before yield: upon app start-up; 
                                  # after yield: upon app shut-down
    """Manage application lifespan events"""
    
    # Function to notify websocket clients (runs in background thread)
    def notify_clients(message):
        try:
            asyncio.run(manager.broadcast(message)) #asyncio.run runs async code from sync code
        except Exception as e:
            print(f"Error notifying clients: {e}")
    
    # Startup: Start the background task to update HR data periodically
    thread = Thread(
        target=update_hr_data_periodically, # this is the function that runs in the thread
        args=(hr_update_frequency_sec, notify_clients), # callback function: notify_clients
        daemon=True
    )
    thread.start()
    print(f"Started periodic HR data updates (every {hr_update_frequency_sec} seconds)")

    yield

    # Shutdown
    print("Shutting down HR data updates...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                print(f"broadcast to: {connection.url=}")
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending to client: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.active_connections.remove(conn)

# Create global connection manager
manager = ConnectionManager()
# websocket
@app.websocket("/ws/heartrate")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for messages
            data = await websocket.receive_text()
            print(f"{data=}")
            # Echo back or handle client messages if needed
            await websocket.send_json({"type": "pong", "message": "Connected"})
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

@app.get("/heartratetimeseries")
async def get_heart_rate_time_series_data():
    """Get the one-time fetched HR data."""
    hr_array = get_hr_data()
    return {"data": hr_array}


@app.get("/heartratetimeseries/live")
async def get_live_heart_rate_data():
    """Get the latest periodically-updated HR data."""
    return {"data": latest_hr_data["data"]}

@app.get("/oura-webhook")
async def verify_oura_webhook(request: Request):
    """
    Oura webhook verification endpoint.
    Required during subscription setup to verify webhook ownership.
    """
    # Get verification token and challenge from query parameters
    print(f"{request=}")
    print(f"{request.query_params=}")
    verification_token = request.query_params.get('verification_token')
    challenge = request.query_params.get('challenge')

    # Get the expected verification token from environment variables
    expected_token = os.getenv('OURA_ACCESS_TOKEN')

    # Verify the token matches
    if verification_token == expected_token:
        # Return the challenge in the required format
        return JSONResponse(content={"challenge": challenge})

    # If verification fails
    raise HTTPException(status_code=401, detail="Invalid verification token")

# Pydantic model for webhook payload
class OuraWebhookEvent(BaseModel):
    event_type: str
    data_type: str
    object_id: str
    user_id: str

async def process_event_async(event_type: str, data_type: str, object_id: str, user_id: str):
    """
    Process webhook event asynchronously.
    This runs in the background after the response is sent.
    """
    try:
        print("Processing Oura webhook event:")
        print(f"  Event Type: {event_type}")
        print(f"  Data Type: {data_type}")
        print(f"  Object ID: {object_id}")
        print(f"  User ID: {user_id}")

        # Add your event processing logic here
        # For example, you might fetch new data from the Oura API based on the event
        # if data_type == "heartrate":
        #     fetch_and_update_heartrate_data(user_id, object_id)

    except Exception as e:
        print(f"Error processing webhook event: {e}")

@app.post("/oura-webhook")
async def process_oura_webhook_event(request: Request, background_tasks: BackgroundTasks):
    """
    Oura webhook event handler.
    Processes incoming webhook events from Oura API.
    Responds quickly (under 10 seconds) and processes event asynchronously.
    """
    # Parse the request body
    body = await request.json()

    # Extract event data
    event_type = body.get('event_type')
    data_type = body.get('data_type')
    object_id = body.get('object_id')
    user_id = body.get('user_id')

    # Add the event processing to background tasks
    background_tasks.add_task(
        process_event_async,
        event_type,
        data_type,
        object_id,
        user_id
    )

    # Respond quickly with 200 OK
    return JSONResponse(content={"status": "OK"}, status_code=200)