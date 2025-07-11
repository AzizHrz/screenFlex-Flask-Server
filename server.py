# ESP32 TV Controller Server v2.1 (Updated for new schedule structure)

from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timedelta
import json
import os
import logging
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
    "MAX_LOG_SIZE": 10 * 1024 * 1024,
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
    app.logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler = RotatingFileHandler(
        os.path.join(CONFIG['LOG_DIR'], 'server.log'),
        maxBytes=CONFIG['MAX_LOG_SIZE'],
        backupCount=CONFIG['LOG_BACKUP_COUNT']
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)

setup_logging()

# ======================
# Helper Functions
# ======================

def validate_time_format(time_str: str) -> bool:
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False

def validate_device_id(device_id: str) -> bool:
    return len(device_id) == 24 and device_id.isalnum()

def load_devices() -> Dict[str, Any]: # changed
    if os.path.exists(CONFIG['DEVICE_DB']):
        with open(CONFIG['DEVICE_DB'], 'r') as f:
            return json.load(f)
    return {}

def save_devices(devices: Dict[str, Any]) -> bool:
    try:
        with open(CONFIG['DEVICE_DB'], 'w') as f:
            json.dump(devices, f, indent=2)
        return True
    except Exception as e:
        app.logger.error(f"DB save failed: {str(e)}")
        return False

def get_device_info(device_id: str) -> Dict[str, Any]:
    devices = load_devices()
    if device_id not in devices:
        devices[device_id] = {
            "firmware_version": "1.0.0",
            "tv_state": "off",
            "schedule": {
                "active": True,
                "timezone": "UTC+1",
                "days": [{"enabled": False, "slots": []} for _ in range(7)]
            },
            "use_schedule": True,
            "logs": []
        }
        save_devices(devices)
    return devices[device_id]

def check_schedule_active(schedule: dict) -> bool: #unused + changed
    """Check if the current time falls within the active schedule."""
    if not schedule.get("active", False):
        return False
    now = datetime.utcnow()
    day_index = now.weekday()
    today = schedule.get("days", [])[day_index] if day_index < len(schedule.get("days", [])) else {}
    if not today.get("enabled", False):
        return False
    now_time = now.time()
    for slot in today.get("slots", []):
        try:
            start = datetime.strptime(slot['start_time'], "%H:%M").time()
            end = datetime.strptime(slot['end_time'], "%H:%M").time()
            if start <= now_time <= end:
                return True
        except:
            continue
    return False

def calculate_next_schedule_change(schedule: dict):#changed + unused
    """Calculate the next schedule change time."""
    if not schedule.get("active", False):
        return None
    now = datetime.utcnow()
    current_time = now.time()
    today_idx = now.weekday()###
    days = schedule.get("days", [])
    for i in range(7):
        idx = (today_idx + i) % 7
        day = days[idx] if idx < len(days) else {}
        if not day.get("enabled", False):
            continue
        for slot in day.get("slots", []):
            try:
                start = datetime.strptime(slot['start_time'], "%H:%M").time()
                future_date = now + timedelta(days=i)
                if i > 0 or (i == 0 and current_time < start):
                    return datetime.combine(future_date.date(), start).isoformat()
            except:
                continue
    return None

def log_device_action(device_id: str, action: str, status: str = "INFO"):
    timestamp = datetime.utcnow().isoformat()
    log_entry = f"{timestamp} | {status} | {action}"
    #    # Save to device-specific log file
    #log_file = os.path.join(CONFIG['LOG_DIR'], f"{device_id}.log")
    #with open(log_file, 'a') as f:
    #    f.write(log_entry + "\n")
    device_info = get_device_info(device_id)
    device_info['logs'].append(log_entry)
    if len(device_info['logs']) > 100:
        device_info['logs'].pop(0)
    devices = load_devices()
    devices[device_id] = device_info
    save_devices(devices)

# ======================
# API Endpoints
# ======================

@app.route('/esp/<string:device_id>/schedule', methods=['GET', 'POST'])
def device_schedule(device_id: str):
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

    data = request.get_json()
    if not data or "days" not in data or "timezone" not in data or "active" not in data:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    for i, day in enumerate(data["days"]):
        if not isinstance(day.get("enabled"), bool):
            return jsonify({"success": False, "error": f"Day {i}: 'enabled' must be bool"}), 400
        for slot in day.get("slots", []):
            if not validate_time_format(slot.get("start_time", "")) or not validate_time_format(slot.get("end_time", "")):
                return jsonify({"success": False, "error": f"Day {i}: invalid time format"}), 400

    update_data = {
        "schedule": {
            "active": data["active"],
            "timezone": data["timezone"],
            "days": data["days"]
        },
        "schedule_updated": datetime.utcnow().isoformat()
    }

    devices = load_devices()
    devices[device_id].update(update_data)
    if not save_devices(devices):
        return jsonify({"success": False, "error": "Database error"}), 500

    log_device_action(device_id, "Schedule updated")
    return jsonify({
        "success": True,
        "message": "Schedule updated successfully",
        "data": {
            "schedule": update_data["schedule"],
            "last_updated": update_data["schedule_updated"]
        }
    })

# ======================
# Main
# ======================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
