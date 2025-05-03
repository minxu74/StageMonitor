from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import json
import time
import threading
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import requests

def query_json_data():

    r = requests.get('https://esgf-node.ornl.gov/esg-search/search?query=project:CMIP6', params= {"format":"application/solr+json", "limit":1})

    return r.json()


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="../frontend/")

DATABASE = "data.db"

# Global variables for cached data
cached_data: Optional[dict] = None
last_update_time: Optional[str] = None

class QueryResult(BaseModel):
    id: int
    timestamp: str
    data: dict

def init_db():
    """Initialize the SQLite database"""
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                data TEXT
            )
        """)
        conn.commit()

def store_data(data: dict):
    """Store data in SQLite"""
    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            "INSERT INTO query_results (timestamp, data) VALUES (?, ?)",
            (datetime.now().isoformat(), json.dumps(data))
        )
        conn.commit()

def get_history(limit: int = 100) -> list[QueryResult]:
    """Retrieve historical data from SQLite"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            "SELECT id, timestamp, data FROM query_results ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return [
            QueryResult(id=row[0], timestamp=row[1], data=json.loads(row[2]))
            for row in cursor.fetchall()
        ]

def update_data_periodically():
    """Background task to update data hourly"""
    global cached_data, last_update_time
    while True:
        try:
            new_data = query_json_data()
            cached_data = new_data
            last_update_time = datetime.now().isoformat()
            store_data(new_data)
            print(f"Data updated at {last_update_time}")
        except Exception as e:
            print(f"Error updating data: {e}")
        time.sleep(3600)  # 1 hour

@app.on_event("startup")
def startup_event():
    """Initialize on startup"""
    init_db()
    # Start background update thread
    threading.Thread(target=update_data_periodically, daemon=True).start()
    # Initial data load
    try:
        global cached_data, last_update_time
        cached_data = query_json_data()
        last_update_time = datetime.now().isoformat()
        store_data(cached_data)
    except Exception as e:
        print(f"Initial data load failed: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/data")
async def get_current_data():
    """Get current data endpoint"""
    if cached_data is None:
        raise HTTPException(status_code=503, detail="Data not available yet")
    return {
        "data": cached_data,
        "last_update": last_update_time
    }

@app.get("/api/history")
async def get_historical_data(limit: int = 100):
    """Get historical data endpoint"""
    return get_history(limit)

@app.post("/api/refresh")
async def refresh_data():
    """Manual refresh endpoint"""
    try:
        global cached_data, last_update_time
        cached_data = query_json_data()
        last_update_time = datetime.now().isoformat()
        store_data(cached_data)
        return {"status": "success", "timestamp": last_update_time}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
