from flask import Flask, request, jsonify
from datetime import datetime
import json

app = Flask(__name__)

# Configuration with enhanced schedule structure
DEVICE_ID = "SOLUTIONGENERIQUE1"
DEVICE_ID = "1"

CONFIG = {
    "current_mode": "schedule",
    "tv_state": "off",
    "schedule": {
        "active": True,
        "timezone": "UTC+1",
        "weekdays": [
            {
                "day": 0,  # Sunday
                "periods": [
                    {"start_time": "09:00", "end_time": "12:00"},
                    {"start_time": "14:00", "end_time": "18:00"}
                ]
            },
            {
                "day": 1,  # Monday
                "periods": [
                    {"start_time": "08:00", "end_time": "20:00"}
                ]
            },
            {
                "day": 2,  # Tuesday
                "periods": [
                    {"start_time": "08:00", "end_time": "20:00"}
                ]
            },
            {
                "day": 3,  # Wednesday
                "periods": [
                    {"start_time": "08:00", "end_time": "20:00"}
                ]
            },
            {
                "day": 4,  # Thursday
                "periods": [
                    {"start_time": "08:00", "end_time": "20:00"}
                ]
            },
            {
                "day": 5,  # Friday
                "periods": [
                    {"start_time": "08:00", "end_time": "20:00"}
                ]
            },
            {
                "day": 6,  # Saturday
                "periods": [
                    {"start_time": "10:00", "end_time": "15:00"}
                ]
            }
        ]
    },
    "wifi_config": {
        "ssid": "test_network",
        "password": "test_password"
    }
}

def generate_schedule_response():
    """Generate the schedule response matching the ESP32 structure"""
    schedule = CONFIG["schedule"]
    response = {
        "active": schedule["active"],
        "timezone": schedule["timezone"],
        "weekdays": schedule["weekdays"]  # Already in correct format
    }
    return response
@app.route('/api/v1/esp/<device_id>/schedul', methods=['GET'])
def schedule(device_id):
    """Get the current schedule for the device"""
    if device_id != DEVICE_ID:
        return jsonify({"success": False, "error": "Invalid device ID"}), 404
    
    response = generate_schedule_response()
    return jsonify({"success": True, "data": response})

@app.route('/api/v1/esp/<device_id>/ping', methods=['POST'])
def handle_ping(device_id):
    """Handle device ping requests with enhanced schedule"""
    try:
        # Parse incoming JSON
        data = request.get_json()
        
        # Log the ping
        print(f"\nReceived ping from {device_id}:")
        print(f"- Actual state: {data.get('actual_state')}")
        print(f"- Desired state: {data.get('desired_state')}")
        print(f"- Device time: {data.get('current_time')}")
        
        # Prepare response
        response = {
            "success": True,
            "data": {
                "mode": CONFIG["current_mode"],
                "tv_state": CONFIG["tv_state"],
                "schedule": generate_schedule_response(),
                "wifi": CONFIG["wifi_config"],
                "server_time": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Error handling ping: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/v1/esp/<device_id>/schedule', methods=['GET', 'POST'])
def handle_schedule(device_id):
    """Handle schedule management"""
    try:
        if request.method == 'GET':
            return jsonify({
                "success": True,
                "data": generate_schedule_response()
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            
            # Validate the schedule structure
            if not all(key in data for key in ['active', 'timezone', 'weekdays']):
                return jsonify({"success": False, "error": "Missing required fields"}), 400
            
            # Validate each day entry
            for day_entry in data['weekdays']:
                if 'day' not in day_entry or 'periods' not in day_entry:
                    return jsonify({"success": False, "error": "Invalid day entry"}), 400
                
                for period in day_entry['periods']:
                    if 'start_time' not in period or 'end_time' not in period:
                        return jsonify({"success": False, "error": "Invalid period entry"}), 400
            
            # Update the schedule
            CONFIG["schedule"] = data
            print(f"\nUpdated schedule for {device_id}:")
            print(json.dumps(data, indent=2))
            
            return jsonify({"success": True})
    
    except Exception as e:
        print(f"Error handling schedule: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 400

# ... (keep the existing wifi, mode, and tv endpoints from previous version)

if __name__ == '__main__':
    print(f"Starting test ping server for device {DEVICE_ID}")
    print("Available endpoints:")
    print(f"- POST /api/v1/esp/{DEVICE_ID}/ping")
    print(f"- GET/POST /api/v1/esp/{DEVICE_ID}/schedule")
    print(f"- POST /api/v1/esp/{DEVICE_ID}/wifi")
    print(f"- POST /api/v1/esp/{DEVICE_ID}/mode")
    print(f"- POST /api/v1/esp/{DEVICE_ID}/tv")
    app.run(host='0.0.0.0', port=5000, debug=True)