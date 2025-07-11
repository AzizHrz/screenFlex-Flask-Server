from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime
import os
# curl "http://192.168.1.173:5000/version"

app = Flask(__name__)

# Configuration
CONFIG = {
    "FIRMWARE_DIR": "firmware",
    "CURRENT_FIRMWARE_VERSION": "1.2.0"
}

# Ensure firmware directory exists
os.makedirs(CONFIG['FIRMWARE_DIR'], exist_ok=True)
DEVICE_ID = "1"

CONFIG = {
    "CURRENT_FIRMWARE_VERSION": "none",
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

@app.route('/<device_id>/schedule', methods=['GET'])
def schedule(device_id):
    """Get the current schedule for the device"""
    if device_id != DEVICE_ID:
        return jsonify({"success": False, "error": "Invalid device ID"}), 404
    
    response = generate_schedule_response()
    return jsonify({"success": True, "data": response})

# ======================
# OTA Update Endpoints
# ======================

@app.route('/version', methods=['GET'])
def get_firmware_version():
    """Endpoint that ESP32 calls to check firmware version"""
    return jsonify({
        "success": True,
        "data": {
            "version": CONFIG["CURRENT_FIRMWARE_VERSION"]
        }
    })

@app.route('/update', methods=['GET'])
def handle_ota_update():
    """Handle OTA firmware download request from ESP32"""
    firmware_file = "firmware.bin"
    firmware_path = os.path.join(CONFIG['FIRMWARE_DIR'], firmware_file)
    
    if not os.path.exists(firmware_path):
        return jsonify({"success": False, "error": "Firmware not found"}), 404
    
    # Get file size
    file_size = os.path.getsize(firmware_path)
    
    # Create a response with proper headers
    response = send_from_directory(
        CONFIG['FIRMWARE_DIR'],
        firmware_file,
        as_attachment=True,
        mimetype='application/octet-stream'
    )
    
    # Set important headers that ESP32 expects
    response.headers['Content-Length'] = file_size
    response.headers['Connection'] = 'close'
    
    return response

# ======================
# WiFi Configuration
# ======================

@app.route('/wifi', methods=['GET'])
def get_wifi_config():
    """Endpoint to provide WiFi credentials (mock)"""
    return jsonify({
        "success": True,
        "data": {
            "ssid": "test_network",
            "password": "test_password"
        }
    })

# ======================
# Server Status
# ======================

@app.route('/ping', methods=['GET'])
def ping():
    """Basic connectivity test endpoint"""
    return jsonify({
        "success": True,
        "message": "Server is online",
        "timestamp": datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)