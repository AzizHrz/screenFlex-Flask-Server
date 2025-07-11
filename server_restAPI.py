"""
ESP32 TV Controller Server v2.0
===============================
Enhanced Features:
- Robust device management with state validation
- Improved TV state control with confirmation
- Schedule management with time validation
- Comprehensive activity logging
- OTA update support
- API documentation
- Better error handling
"""

from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime
import time 
import json
import hashlib
import logging
import os
import requests
from datetime import timedelta

from logging.handlers import RotatingFileHandler
from typing import Dict, Any

app = Flask(__name__)

# ======================
# Configuration
# ======================

CONFIG = {
    "LOG_DIR": "logs",
    "FIRMWARE_DIR": "firmware",
    "DEVICE_DB": "devices.json",
    "MAX_LOG_SIZE": 10 * 1024 * 1024,  # 10MB
    "LOG_BACKUP_COUNT": 5,
    "CURRENT_FIRMWARE_VERSION": "1.2.0",
    "ALLOWED_EXTENSIONS": {'bin'}
}

# Ensure directories exist
os.makedirs(CONFIG['LOG_DIR'], exist_ok=True)
os.makedirs(CONFIG['FIRMWARE_DIR'], exist_ok=True)

# ======================
# Logging Setup
# ======================
def setup_logging():
    """Configure comprehensive logging with file rotation"""
    app.logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        os.path.join(CONFIG['LOG_DIR'], 'server.log'),
        maxBytes=CONFIG['MAX_LOG_SIZE'],
        backupCount=CONFIG['LOG_BACKUP_COUNT']
    )
    file_handler.setFormatter(formatter)
    
    # Console output
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)

setup_logging()

# ======================
# Helper Functions
# ======================


def version_to_tuple(version_str: str) -> tuple:
    """Convert version string to comparable tuple"""
    return tuple(map(int, version_str.split('.')))

def is_newer_version(current: str, available: str) -> bool:
    """Compare version strings"""
    return version_to_tuple(available) > version_to_tuple(current)

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in CONFIG['ALLOWED_EXTENSIONS']

def validate_device_id(device_id: str) -> bool:
    """Validate device ID format (24-char alphanumeric)"""
    return len(device_id) == 24 and device_id.isalnum()

def load_devices() -> Dict[str, Any]:
    """Load all devices from database"""
    try:
        if os.path.exists(CONFIG['DEVICE_DB']):
            with open(CONFIG['DEVICE_DB'], 'r') as f:
                devices = json.load(f)
                # Ensure all devices have required fields
                for device_id, info in devices.items():
                    if 'firmware_version' not in info:
                        info['firmware_version'] = "1.0.0"
                    if 'tv_state' not in info:
                        info['tv_state'] = 'off'
                    if 'schedule' not in info:
                        info['schedule'] = {
                            "active": True,
                            "timezone": "UTC+1",
                            "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
                            "start_time": "08:00",
                            "end_time": "20:00"
                        }
                return devices
        return {}
    except (json.JSONDecodeError, IOError) as e:
        app.logger.error(f"Failed to load devices: {str(e)}")
        return {}

def get_device_info(device_id: str) -> Dict[str, Any]:
    """Get device info with default values"""
    devices = load_devices()
    if device_id not in devices:
        devices[device_id] = {
            "firmware_version": "1.0.0",
            "tv_state": "off",
            "schedule": {
                "active": True,
                "timezone": "UTC+1",
                "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
                "start_time": "08:00",
                "end_time": "20:00"
            },
            "last_seen": None,
            "last_update": None,
            "logs": []
        }
        save_devices(devices)
    return devices[device_id]

def save_devices(devices: Dict[str, Any]) -> bool:
    """Save devices to database"""
    try:
        with open(CONFIG['DEVICE_DB'], 'w') as f:
            json.dump(devices, f, indent=2)
        return True
    except Exception as e:
        app.logger.error(f"DB save failed: {str(e)}")
        return False

def log_device_action(device_id: str, action: str, status: str = "INFO"):
    """Log device action with timestamp"""
    timestamp = datetime.utcnow().isoformat()
    log_entry = f"{timestamp} | {status.upper()} | {action}"
    
    # Save to device-specific log file
    log_file = os.path.join(CONFIG['LOG_DIR'], f"{device_id}.log")
    with open(log_file, 'a') as f:
        f.write(log_entry + "\n")
    
    # Keep in memory (last 100 entries)
    device_info = get_device_info(device_id)
    device_info['logs'].append(log_entry)
    if len(device_info['logs']) > 100:
        device_info['logs'].pop(0)
    
    devices = load_devices()
    devices[device_id] = device_info
    save_devices(devices)


def save_device_info(device_id: str, update_data: dict) -> bool:
    """Update specific device information"""
    devices = load_devices()
    if device_id not in devices:
        return False
    
    devices[device_id].update(update_data)
    return save_devices(devices)

def validate_time_format(time_str: str) -> bool:
    """Validate HH:MM format"""
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False

def check_schedule_active(schedule):
    """Check if schedule should be active now"""
    if not schedule["active"]:
        return False
        
    # Get current day and time
    now = datetime.utcnow()
    current_day = now.strftime("%a")  # "Mon", "Tue", etc.
    current_time = now.strftime("%H:%M")
    
    # Check day
    if current_day not in schedule["weekdays"]:
        return False
    
    # Check time
    start_time = datetime.strptime(schedule["start_time"], "%H:%M").time()
    end_time = datetime.strptime(schedule["end_time"], "%H:%M").time()
    current_time = now.time()
    
    return start_time <= current_time <= end_time

def calculate_next_schedule_change(schedule):
    """Calculate when the schedule will next change state"""
    if not schedule["active"]:
        return None
        
    now = datetime.utcnow()
    current_day = now.strftime("%a")
    current_time = now.time()
    
    start_time = datetime.strptime(schedule["start_time"], "%H:%M").time()
    end_time = datetime.strptime(schedule["end_time"], "%H:%M").time()
    
    # If currently in schedule time, next change is end time
    if current_day in schedule["weekdays"] and start_time <= current_time <= end_time:
        next_change = datetime.combine(now.date(), end_time)
        return next_change.isoformat()
    
    # Otherwise find next start time
    days_ahead = 0
    for i in range(1, 8):  # Check next 7 days
        next_day = (now + timedelta(days=i)).strftime("%a")
        if next_day in schedule["weekdays"]:
            days_ahead = i
            break
    
    if days_ahead > 0:
        next_date = now.date() + timedelta(days=days_ahead)
        next_change = datetime.combine(next_date, start_time)
        return next_change.isoformat()
    
    return None

def get_wifi_config_for_device(device_id: str):
    """
    Retrieve the WiFi configuration for a specific device.
    Returns a dict with 'ssid' and 'password' if available, None otherwise.
    """
    device_info = get_device_info(device_id)
    return device_info.get("wifi_config")


# ======================
# API Endpoints
# ======================

@app.route('/esp/<device_id>/wifi', methods=['GET'])
def get_wifi_config(device_id):
    # Get WiFi config from your database or configuration
    wifi_config = get_wifi_config_for_device(device_id)  # Implement this
    
    if wifi_config:
        return jsonify({
            "success": True,
            "data": {
                "ssid": wifi_config['ssid'],
                "password": wifi_config['password']
            }
        })
    else:
        return jsonify({"success": False, "error": "No WiFi config found"}), 404

@app.route('/esp/<string:device_id>/wifi', methods=['POST'])
def set_wifi_config(device_id: str):
    data = request.get_json()
    if not data or 'ssid' not in data or 'password' not in data:
        return jsonify({"success": False, "error": "Missing ssid or password"}), 400
    
    update_data = {
        "wifi_config": {
            "ssid": data["ssid"],
            "password": data["password"]
        },
        "wifi_updated": datetime.utcnow().isoformat()
    }
    
    if not save_device_info(device_id, update_data):
        return jsonify({"success": False, "error": "Database error"}), 500
    
    return jsonify({
        "success": True,
        "message": "WiFi config updated"
    })

@app.route('/esp/<device_id>/firmware', methods=['GET'])
def handle_firmware_check(device_id):
    device_info = get_device_info(device_id)
    current_version = device_info.get("firmware_version", "1.0.0")
    latest_version = CONFIG['CURRENT_FIRMWARE_VERSION']
    
    return jsonify({
        "success": True,
        "data": {
            "current_version": current_version,
            "latest_version": latest_version,
            "update_available": is_newer_version(current_version, latest_version),
            "url": f"http://{request.host}/firmware/download/{device_id}.bin"
        }
    })

def handle_firmware_upload(device_id: str):
    """Handle firmware upload"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No firmware file"}), 400
    
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Invalid file type"}), 400

    # Save the firmware file
    filename = f"{device_id}.bin"
    filepath = os.path.join(CONFIG['FIRMWARE_DIR'], filename)
    file.save(filepath)
    
    # Update device info
    version = request.form.get("version", CONFIG['CURRENT_FIRMWARE_VERSION'])
    devices = load_devices()
    devices[device_id].update({
        "firmware_version": version,
        "last_update": datetime.utcnow().isoformat()
    })
    save_devices(devices)
    
    log_device_action(device_id, f"Firmware updated to v{version}")
    return jsonify({
        "success": True,
        "message": "Firmware uploaded successfully",
        "data": {
            "filename": filename,
            "version": version,
            "size": os.path.getsize(filepath),
            
        }
    })

@app.route('/esp/<string:device_id>/ping', methods=['POST'])
def ping_device(device_id: str):
    if not validate_device_id(device_id):
        return jsonify({"success": False, "error": "Invalid device ID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Missing JSON data"}), 400

    devices = load_devices()
    device_info = get_device_info(device_id)

    # === Update device info from ping payload ===
    if 'actual_state' in data:
        device_info['actual_state'] = data['actual_state']

    if 'desired_state' in data:
        device_info['tv_state'] = data['desired_state']
        device_info['desired_state'] = data['desired_state']  # Optional: keep both keys

    if 'current_time' in data:
        device_info['last_seen'] = data['current_time']

    # Always update last ping timestamp
    device_info['last_ping'] = datetime.utcnow().isoformat()

    # Save updated device info
    devices[device_id] = device_info
    save_devices(devices)

    # === Return response to device ===
    return jsonify({
        "success": True,
        "data": {
            "use_schedule": device_info.get("use_schedule", True),
            "tv_state": device_info.get("tv_state", "off"),
            "schedule": device_info.get("schedule", {}),
            "firmware_version": device_info.get("firmware_version", "1.0.0"),
            "latest_firmware_version": CONFIG["CURRENT_FIRMWARE_VERSION"],
            "current_time": datetime.utcnow().isoformat(),
            "server_time": datetime.utcnow().isoformat()
        }
    })

@app.route('/firmware/download/<path:filename>')
def download_firmware(filename: str):
    """Serve firmware files for download"""
    if not validate_device_id(filename.split('.')[0]):
        return jsonify({"success": False, "error": "Invalid device ID"}), 400
    
    try:
        return send_from_directory(
            CONFIG['FIRMWARE_DIR'],
            filename,
            as_attachment=True,
            mimetype='application/octet-stream'
        )
    except FileNotFoundError:
        return jsonify({"success": False, "error": "Firmware not found"}), 404

@app.route('/esp/<string:device_id>/tv', methods=['GET', 'POST'])
def tv_control(device_id: str):
    """
    Enhanced TV Control Endpoint
    - GET: Returns both commanded and actual states
    - POST: Updates commanded state with proper validation
    """
    if not validate_device_id(device_id):
        return jsonify({"success": False, "error": "Invalid device ID"}), 400
    
    device_info = get_device_info(device_id)
    current_state = device_info.get("actual_state", "unknown").lower()
    
    if request.method == 'GET':
        log_device_action(device_id, "TV state queried")
        return jsonify({
            "success": True,
            "data": {
                "commanded_state": device_info["tv_state"],
                "actual_state": current_state,
                "last_command": device_info.get("last_command"),
                "last_actual_report": device_info.get("last_actual_report")
            }
        })
    
    # POST method handling
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({"success": False, "error": "Missing status"}), 400
    
    requested_status = data['status'].lower()
    if requested_status not in ['on', 'off']:
        return jsonify({"success": False, "error": "Invalid status"}), 400
    
    # Check if the TV is already in the requested state
    if current_state == requested_status:
        message = f"TV is already {requested_status}"
        log_device_action(device_id, message)
        return jsonify({
            "success": True,
            "message": message,
            "should_update": True,
            "data": {
                "current_state": current_state,
                "commanded_state": device_info["tv_state"]
            }
        })
    
    # Update commanded state
    update_data = {
        "tv_state": requested_status,
        "last_command": datetime.utcnow().isoformat(),
        "last_seen": datetime.utcnow().isoformat()
    }
    
    if not save_device_info(device_id, update_data):
        return jsonify({"success": False, "error": "Database error"}), 500
    
    log_device_action(device_id, f"TV commanded to turn {requested_status}")
    
    return jsonify({
        "success": True,
        "message": f"TV commanded to turn {requested_status}",
        "should_update": True,
        "data": {
            "previous_state": current_state,
            "commanded_state": requested_status
        }
    })

@app.route('/esp/<string:device_id>/mode', methods=['GET', 'POST'])
def device_mode(device_id: str):
    """
    Mode Management Endpoint
    ---
    GET: Fetch the current mode (use_schedule)
    POST: Update the mode (requires 'use_schedule' field)
    """
    if not validate_device_id(device_id):
        return jsonify({"success": False, "error": "Invalid device ID"}), 400
    
    device_info = get_device_info(device_id)
    
    if request.method == 'GET':
        # Return the current mode
        log_device_action(device_id, "Mode queried")
        return jsonify({
            "success": True,
            "data": {
                "use_schedule": device_info.get("use_schedule", True),  # Default to True
                "last_updated": device_info.get("last_mode_update")
            }
        })
    
    # POST method handling
    data = request.get_json()
    if not data or 'use_schedule' not in data:
        return jsonify({"success": False, "error": "Missing 'use_schedule' field"}), 400
    
    use_schedule = bool(data['use_schedule'])
    
    # Update the mode
    update_data = {
        "use_schedule": use_schedule,
        "last_mode_update": datetime.utcnow().isoformat()
    }
    
    if not save_device_info(device_id, update_data):
        return jsonify({"success": False, "error": "Database error"}), 500
    
    action = f"Mode updated to {'schedule' if use_schedule else 'server commands'}"
    log_device_action(device_id, action)
    
    return jsonify({
        "success": True,
        "message": action,
        "data": {
            "use_schedule": use_schedule,
            "last_updated": update_data["last_mode_update"]
        }
    })

@app.route('/esp/<string:device_id>/state', methods=['POST'])
def report_tv_state(device_id: str):
    """Endpoint for device to report actual TV state"""
    if not validate_device_id(device_id):
        return jsonify({"success": False, "error": "Invalid device ID"}), 400
    
    data = request.get_json()
    if not data or 'actual_state' not in data:
        return jsonify({"success": False, "error": "Missing actual_state"}), 400
    
    state = data['actual_state'].lower()
    if state not in ['on', 'off']:
        return jsonify({"success": False, "error": "Invalid state"}), 400
    
    # Update actual state
    update_data = {
        "actual_state": state,
        "last_actual_report": datetime.utcnow().isoformat(),
        "last_seen": datetime.utcnow().isoformat()
    }
    
    if not save_device_info(device_id, update_data):
        return jsonify({"success": False, "error": "Database error"}), 500
    
    log_device_action(device_id, f"Reported actual TV state: {state}")
    
    return jsonify({
        "success": True,
        "message": "TV state reported",
        "data": {
            "actual_state": state
        }
    })

@app.route('/esp/<string:device_id>/schedule', methods=['GET', 'POST'])

def device_schedule(device_id: str):
     """
     Schedule Management Endpoint
     ---
     GET: Returns current schedule
     POST: Updates schedule (requires all schedule fields)
     """
     if not validate_device_id(device_id):
         return jsonify({"success": False, "error": "Invalid device ID"}), 400
     
     device_info = get_device_info(device_id)
     
     if request.method == 'GET':
         log_device_action(device_id, "Schedule queried")
         return jsonify({
             "success": True,
             "data": {
                 "schedule": device_info["schedule"],
                 "last_updated": device_info.get("schedule_updated")
             }
         })
     
     # POST method handling
     data = request.get_json()
     if not data:
         return jsonify({"success": False, "error": "Invalid data"}), 400
     
     # Validate required fields
     required_fields = ['active', 'timezone', 'weekdays', 'start_time', 'end_time']
     if not all(field in data for field in required_fields):
         return jsonify({
             "success": False,
             "error": "Missing required fields",
             "required": required_fields
         }), 400
     
     # Validate time format
     if not validate_time_format(data['start_time']):
         return jsonify({
             "success": False,
             "error": "Invalid start_time format (HH:MM)"
         }), 400
         
     if not validate_time_format(data['end_time']):
         return jsonify({
             "success": False,
             "error": "Invalid end_time format (HH:MM)"
         }), 400
     
    # Update schedule
     update_data = {
         "schedule": {
             "active": data["active"],
             "timezone": data["timezone"],
             "weekdays": data["weekdays"],
             "start_time": data["start_time"],
             "end_time": data["end_time"]
         },
         "schedule_updated": datetime.utcnow().isoformat()
     }
     
     if not save_device_info(device_id, update_data):
         return jsonify({"success": False, "error": "Database error"}), 500
     
     log_device_action(device_id, "Schedule updated")
     
     return jsonify({
         "success": True,
         "message": "Schedule updated successfully",
         "should_update": True,
         "data": {
             "schedule": update_data["schedule"],
             "last_updated": update_data["schedule_updated"]
         }
     })




@app.route('/esp/<string:device_id>/status', methods=['GET'])
def device_status(device_id: str):
    """Get complete device status including mode and command"""
    if not validate_device_id(device_id):
        return jsonify({"success": False, "error": "Invalid device ID"}), 400
    
    device_info = get_device_info(device_id)
    log_device_action(device_id, "Full status requested")
    
    return jsonify({
        "success": True,
        "data": {
            "tv": {
                "commanded_state": device_info["tv_state"],
                "actual_state": device_info.get("actual_state", "unknown"),
                "last_command": device_info.get("last_command"),
                "last_actual_report": device_info.get("last_actual_report")
            },
            "mode": {
                "use_schedule": device_info.get("use_schedule", True),
                "last_mode_update": device_info.get("last_mode_update")
            },
            "schedule": device_info["schedule"],
            "device": {
                "firmware_version": device_info.get("firmware_version", "1.0.0"),
                "last_seen": device_info.get("last_seen"),
                "is_online": device_info.get("is_online", False)
            }
        }
    })

# ======================
# Error Handlers
# ======================
@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"success": False, "error": "Internal server error"}), 500

# ======================
# Main Application
# ======================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False) 