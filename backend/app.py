from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import json
import time
import threading
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
import requests

from facet_query import facet_query

#from metadata_migrate_sync.app import 

indexes = ["public", "CMIP6Plus", "DRCDP", "e3sm", "obs4MIPs", "input4MIPs"]

def query_json_data(index_name: str) -> dict[Any, Any]:

    #r = requests.get('https://esgf-node.ornl.gov/esg-search/search?query=project:CMIP6', params= {"format":"application/solr+json", "limit":1})

    #return r.json()
    if index_name == "public":
        return facet_query(ep_name="public", project = "CMIP6")
        #-return {'esgf-node.ornl.gov': {
        #-            'total_items': 34960355, 
        #-            'projects': {
        #-                 'CMIP6': 32807528, 'CMIP5': 2036503, 'CMIP3': 111503, 'e3sm-supplement': 3225, 'input4MIPs': 1444, 'obs4MIPs': 152
        #-            }
        #-        }, 
        #-        'eagle.alcf.anl.gov': {
        #-            'total_items': 30967797, 
        #-            'projects': {
        #-                'CMIP6': 28822831, 'CMIP5': 2018420, 'CMIP3': 111503, 'input4MIPs': 14896, 'obs4MIPs': 147
        #-            }
        #-        }, 
        #-        'aims3.llnl.gov': {
        #-            'total_items': 4170883, 
        #-            'projects': {
        #-                'CMIP5': 2036503, 'CMIP6': 2005809, 'CMIP3': 111503, 'input4MIPs': 13805, 'e3sm-supplement': 3225, 'obs4MIPs': 38 
        #-             }
        #-        }, 
        #-        'esgf-data1.llnl.gov': {
        #-            'total_items': 32660846, 
        #-            'projects': {'CMIP6': 32660834, 'obs4MIPs': 12
        #-            }
        #-        }, 
        #-        'esgf-data2.llnl.gov': {
        #-            'total_items': 266379, 
        #-            'projects': {'CMIP6': 253187, 'input4MIPs': 6701, 'DRCDP': 5727, 'obs4MIPs': 746, 'CMIP6Plus': 18
        #-            }
        #-        }
        #-       }

    else:
        #-return {
        #-    'obs4MIPs': {
        #-         'total_items': 1397, 
        #-         'institution_id': {
        #-              'NASA-GSFC': 367, 
        #-              'ECMWF': 360, 
        #-              'NASA-JPL': 120, 
        #-              'NASA-LaRC': 88, 
        #-              'ESSO': 22, 
        #-              'RSS': 22, 
        #-              'CNES': 6, 
        #-              'NOAA-ESRL-PSD': 6, 
        #-              'MOHC': 2
        #-         }
        #-    }
        #-}
        return facet_query(ep_name="stage", project = index_name)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="../frontend/")

# database
DATABASE = "data_new.db"

# Global variables for cached data
cached_data: Optional[dict] = None
last_update_time: Optional[str] = None

class QueryResult(BaseModel):
    id: int
    timestamp: str
    index: str
    data: dict

def init_db():
    """Initialize the SQLite database"""
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                indexname TEXT,
                data TEXT
            )
        """)
        conn.commit()

def store_data(index_name: str, data: dict):
    """Store data in SQLite"""
    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            "INSERT INTO query_results (timestamp, indexname, data) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), index_name, json.dumps(data))
        )
        conn.commit()

def get_history(index_name: str, limit: int = 100) -> list[QueryResult]:
    """Retrieve historical data from SQLite"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            """SELECT id, timestamp, indexname, data 
               FROM query_results 
               WHERE indexname = ?
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (index_name, limit)
        )
        return [
            QueryResult(
                id=row[0], 
                timestamp=row[1], 
                index=row[2], 
                data=json.loads(row[3]))
            for row in cursor.fetchall()
        ]

def update_data_periodically():
    """Background task to update data hourly"""
    global cached_data, last_update_time
    while True:
        try:
            for index_name in indexes:
                new_data = query_json_data(index_name)
                last_update_time = datetime.now().isoformat()
                store_data(index_name, new_data)
                cached_data[index_name] = get_history(index_name, limit=3)
            print(f"Data updated at {last_update_time}")
        except Exception as e:
            print(f"Error updating data: {e}")
        time.sleep(10800)  # 1 hour

@app.on_event("startup")
def startup_event():
    """Initialize on startup"""
    init_db()
    # Start background update thread
    threading.Thread(target=update_data_periodically, daemon=True).start()
    # Initial data load
    try:
        global cached_data, last_update_time

        cached_data = {}
        for index_name in indexes:
            new_data = query_json_data(index_name)
            last_update_time = datetime.now().isoformat()
            store_data(index_name, new_data)
            cached_data[index_name] = [{"data": new_data}]

            print ('xxxx', index_name);
    except Exception as e:
        print(f"Initial data load failed: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/{index_name}")
async def get_current_data(index_name: str):
    """Get current data endpoint"""
    if cached_data[index_name] is None:
        raise HTTPException(status_code=503, detail="Data not available yet")
    return {
        "data": cached_data[index_name],
        "last_update": last_update_time
    }

#@app.get("/api/history")
#async def get_historical_data(limit: int = 100):
#    """Get historical data endpoint"""
#    return get_history(limit)

@app.post("/api/refresh")
async def refresh_data():
    """Manual refresh endpoint"""
    try:
        global cached_data, last_update_time
        for index_name in indexes:
            new_data = query_json_data(index_name)
            last_update_time = datetime.now().isoformat()
            store_data(index_name, new_data)
            cached_data[index_name] = get_history(index_name, limit=3)
        return {"status": "success", "timestamp": last_update_time}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
