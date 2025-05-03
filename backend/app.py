# app.py
from flask import Flask, jsonify, render_template
import time
import threading
import json
#from your_query_module import query_json_data  # Import your existing query function
import requests



def query_json_data():

    r = requests.get('https://esgf-node.ornl.gov/esg-search/search?query=project:CMIP6', params= {"format":"application/solr+json", "limit":1})

    return r.json()

app = Flask(__name__)

# Global variable to store cached data
cached_data = None
last_update_time = 0

def update_data():
    """Function to update data periodically"""
    global cached_data, last_update_time
    while True:
        try:
            # Call your existing query function here
            new_data = query_json_data()
            cached_data = new_data
            last_update_time = time.time()
            print("Data updated successfully")
        except Exception as e:
            print(f"Error updating data: {e}")
        # Sleep for 1 hour (3600 seconds)
        time.sleep(3600)

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    """API endpoint to get the current data"""
    if cached_data is None:
        return jsonify({"error": "Data not available yet"}), 503
    return jsonify({
        "data": cached_data,
        "last_update": last_update_time
    })

@app.route('/api/force-update', methods=['POST'])
def force_update():
    """Endpoint to manually trigger an update"""
    global cached_data, last_update_time
    try:
        new_data = query_json_data()
        cached_data = new_data
        last_update_time = time.time()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Start the update thread when the app starts
    update_thread = threading.Thread(target=update_data)
    update_thread.daemon = True
    update_thread.start()
    
    # Initial data load
    try:
        cached_data = query_json_data()
        last_update_time = time.time()
    except Exception as e:
        print(f"Initial data load failed: {e}")
    
    app.run(debug=True)
