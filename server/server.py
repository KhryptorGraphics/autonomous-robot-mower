#!/usr/bin/env python3
"""
Robot Mower Control Server
Provides a web interface for controlling and monitoring the robot mower
"""
import os
import time
import json
import base64
import logging
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
import eventlet

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MowerServer")

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'robotmower2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Create directories for storing data
os.makedirs('static/images', exist_ok=True)
os.makedirs('logs', exist_ok=True)

# Global variables
connected_mowers = {}
latest_frame = None
latest_objects = []
recording = False
record_start_time = None
record_frames = []

# Routes
@app.route('/')
def index():
    """Serve the main control interface"""
    return render_template('index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/api/status')
def get_status():
    """Get the status of all connected mowers"""
    return jsonify(connected_mowers)

@app.route('/api/snapshot', methods=['POST'])
def take_snapshot():
    """Take a snapshot of the current video frame"""
    global latest_frame
    
    if latest_frame is None:
        return jsonify({'error': 'No video frame available'}), 400
    
    # Save the frame as an image
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"static/images/snapshot_{timestamp}.jpg"
    
    # Convert the frame to an image and save it
    cv2.imwrite(filename, latest_frame)
    
    return jsonify({
        'success': True,
        'filename': filename,
        'url': f"/static/images/snapshot_{timestamp}.jpg"
    })

@app.route('/api/start_recording', methods=['POST'])
def start_recording():
    """Start recording video"""
    global recording, record_start_time, record_frames
    
    if recording:
        return jsonify({'error': 'Already recording'}), 400
    
    recording = True
    record_start_time = datetime.now()
    record_frames = []
    
    logger.info("Started recording")
    
    return jsonify({
        'success': True,
        'start_time': record_start_time.isoformat()
    })

@app.route('/api/stop_recording', methods=['POST'])
def stop_recording():
    """Stop recording video and save it"""
    global recording, record_frames
    
    if not recording:
        return jsonify({'error': 'Not recording'}), 400
    
    recording = False
    
    if len(record_frames) == 0:
        return jsonify({'error': 'No frames recorded'}), 400
    
    # Save the video
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"static/images/recording_{timestamp}.avi"
    
    # Get frame dimensions from the first frame
    height, width, _ = record_frames[0].shape
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(filename, fourcc, 10.0, (width, height))
    
    # Write frames to video
    for frame in record_frames:
        out.write(frame)
    
    out.release()
    
    logger.info(f"Saved recording to {filename}")
    
    return jsonify({
        'success': True,
        'filename': filename,
        'url': f"/static/images/recording_{timestamp}.avi",
        'frame_count': len(record_frames)
    })

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('server_status', {'status': 'connected', 'time': datetime.now().isoformat()})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('mower_status')
def handle_mower_status(data):
    """Handle mower status updates"""
    logger.debug(f"Received mower status: {data}")
    
    # Store the mower status
    mower_id = request.sid
    connected_mowers[mower_id] = {
        'status': data,
        'last_update': datetime.now().isoformat()
    }
    
    # Broadcast to all clients
    emit('mower_status_update', {
        'mower_id': mower_id,
        'status': data,
        'time': datetime.now().isoformat()
    }, broadcast=True)

@socketio.on('video_frame')
def handle_video_frame(data):
    """Handle video frame from mower"""
    global latest_frame, latest_objects
    
    try:
        # Decode the frame
        frame_data = data.get('frame')
        if frame_data:
            # Convert bytes to numpy array
            nparr = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Store the latest frame
            latest_frame = frame
            latest_objects = data.get('objects', [])
            
            # If recording, add frame to record_frames
            if recording:
                record_frames.append(frame.copy())
            
            # Convert to base64 for sending to clients
            _, buffer = cv2.imencode('.jpg', frame)
            base64_frame = base64.b64encode(buffer).decode('utf-8')
            
            # Broadcast to all clients
            emit('video_update', {
                'frame': base64_frame,
                'objects': latest_objects,
                'timestamp': data.get('timestamp', datetime.now().isoformat())
            }, broadcast=True)
    
    except Exception as e:
        logger.error(f"Error processing video frame: {e}")

@socketio.on('command')
def handle_command(data):
    """Handle command from client to mower"""
    logger.info(f"Received command: {data}")
    
    # Forward the command to the mower
    emit('command', data, broadcast=True)

@socketio.on('heartbeat')
def handle_heartbeat(data):
    """Handle heartbeat from client"""
    # Send heartbeat to all mowers
    emit('heartbeat', {
        'time': datetime.now().isoformat()
    }, broadcast=True)

@socketio.on('obstacle_detected')
def handle_obstacle(data):
    """Handle obstacle detection from mower"""
    logger.warning(f"Obstacle detected: {data}")
    
    # Broadcast to all clients
    emit('obstacle_alert', {
        'distance': data.get('distance'),
        'time': datetime.now().isoformat()
    }, broadcast=True)

# Heartbeat thread
def heartbeat_thread():
    """Send periodic heartbeats to keep connections alive"""
    while True:
        socketio.emit('heartbeat', {
            'server_time': datetime.now().isoformat()
        })
        
        # Clean up old mowers
        current_time = datetime.now()
        mowers_to_remove = []
        
        for mower_id, mower_data in connected_mowers.items():
            last_update = datetime.fromisoformat(mower_data['last_update'])
            if (current_time - last_update).total_seconds() > 30:
                mowers_to_remove.append(mower_id)
        
        for mower_id in mowers_to_remove:
            logger.warning(f"Removing disconnected mower: {mower_id}")
            del connected_mowers[mower_id]
        
        time.sleep(5)

# Create templates directory and index.html
def create_templates():
    """Create the templates directory and index.html file"""
    os.makedirs('templates', exist_ok=True)
    
    with open('templates/index.html', 'w') as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Robot Mower Control</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css">
    <script src="https://cdn.jsdelivr.net/npm/socket.io-client@4.5.1/dist/socket.io.min.js"></script>
    <style>
        body {
            padding-top: 20px;
            background-color: #f5f5f5;
        }
        .video-container {
            position: relative;
            width: 100%;
            max-width: 640px;
            margin: 0 auto;
            border: 2px solid #333;
            border-radius: 5px;
            overflow: hidden;
        }
        .video-feed {
            width: 100%;
            height: auto;
            display: block;
        }
        .control-panel {
            margin-top: 20px;
            padding: 15px;
            background-color: #fff;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .direction-controls {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            grid-gap: 10px;
            margin: 20px 0;
        }
        .direction-btn {
            padding: 15px;
            font-size: 18px;
        }
        .status-indicator {
            display: inline-block;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .status-online {
            background-color: #28a745;
        }
        .status-offline {
            background-color: #dc3545;
        }
        .battery-indicator {
            height: 20px;
            border-radius: 5px;
            margin-top: 5px;
        }
        .obstacle-alert {
            color: #dc3545;
            font-weight: bold;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="text-center mb-4">Robot Mower Control Panel</h1>
        
        <div class="row">
            <div class="col-md-8">
                <div class="video-container">
                    <img id="video-feed" class="video-feed" src="/static/images/no-video.jpg" alt="Video Feed">
                    <div id="obstacle-alert" class="alert alert-danger obstacle-alert m-2 position-absolute top-0 end-0">
                        Obstacle Detected!
                    </div>
                </div>
                
                <div class="d-flex justify-content-between mt-2">
                    <button id="snapshot-btn" class="btn btn-primary">Take Snapshot</button>
                    <button id="record-btn" class="btn btn-danger">Start Recording</button>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="control-panel">
                    <h3>Status</h3>
                    <div class="mb-3">
                        <span id="connection-status" class="status-indicator status-offline"></span>
                        <span id="connection-text">Disconnected</span>
                    </div>
                    
                    <div class="mb-3">
                        <label>Battery Level:</label>
                        <div class="progress battery-indicator">
                            <div id="battery-level" class="progress-bar bg-success" role="progressbar" style="width: 0%"></div>
                        </div>
                        <span id="battery-percentage">0%</span>
                    </div>
                    
                    <div class="mb-3">
                        <label>Movement Status:</label>
                        <span id="movement-status">Stopped</span>
                    </div>
                    
                    <div class="mb-3">
                        <label>Blade Status:</label>
                        <span id="blade-status">Inactive</span>
                    </div>
                    
                    <div class="form-check form-switch mb-3">
                        <input class="form-check-input" type="checkbox" id="autonomous-switch">
                        <label class="form-check-label" for="autonomous-switch">Autonomous Mode</label>
                    </div>
                </div>
                
                <div class="control-panel mt-3">
                    <h3>Controls</h3>
                    
                    <div class="direction-controls">
                        <button class="btn btn-secondary direction-btn" data-direction="left">
                            <i class="bi bi-arrow-left"></i> Left
                        </button>
                        <button class="btn btn-primary direction-btn" data-direction="forward">
                            <i class="bi bi-arrow-up"></i> Forward
                        </button>
                        <button class="btn btn-secondary direction-btn" data-direction="right">
                            <i class="bi bi-arrow-right"></i> Right
                        </button>
                        <button class="btn btn-secondary direction-btn" data-direction="stop">
                            <i class="bi bi-stop-fill"></i> Stop
                        </button>
                        <button class="btn btn-primary direction-btn" data-direction="backward">
                            <i class="bi bi-arrow-down"></i> Back
                        </button>
                        <button class="btn btn-secondary direction-btn" id="blade-toggle">
                            <i class="bi bi-scissors"></i> Blade
                        </button>
                    </div>
                    
                    <div class="mb-3">
                        <label for="speed-slider" class="form-label">Speed: <span id="speed-value">50</span>%</label>
                        <input type="range" class="form-range" id="speed-slider" min="0" max="100" value="50">
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-12">
                <div class="control-panel">
                    <h3>Log</h3>
                    <div id="log-container" style="height: 200px; overflow-y: auto; background-color: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace;">
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Initialize Socket.IO
        const socket = io();
        let isRecording = false;
        let bladeActive = false;
        
        // DOM elements
        const videoFeed = document.getElementById('video-feed');
        const obstacleAlert = document.getElementById('obstacle-alert');
        const connectionStatus = document.getElementById('connection-status');
        const connectionText = document.getElementById('connection-text');
        const batteryLevel = document.getElementById('battery-level');
        const batteryPercentage = document.getElementById('battery-percentage');
        const movementStatus = document.getElementById('movement-status');
        const bladeStatus = document.getElementById('blade-status');
        const autonomousSwitch = document.getElementById('autonomous-switch');
        const snapshotBtn = document.getElementById('snapshot-btn');
        const recordBtn = document.getElementById('record-btn');
        const speedSlider = document.getElementById('speed-slider');
        const speedValue = document.getElementById('speed-value');
        const bladeToggle = document.getElementById('blade-toggle');
        const logContainer = document.getElementById('log-container');
        
        // Socket.IO events
        socket.on('connect', () => {
            connectionStatus.classList.remove('status-offline');
            connectionStatus.classList.add('status-online');
            connectionText.textContent = 'Connected';
            logMessage('Connected to server');
            
            // Start sending heartbeats
            setInterval(() => {
                socket.emit('heartbeat', { time: new Date().toISOString() });
            }, 5000);
        });
        
        socket.on('disconnect', () => {
            connectionStatus.classList.remove('status-online');
            connectionStatus.classList.add('status-offline');
            connectionText.textContent = 'Disconnected';
            logMessage('Disconnected from server', 'error');
        });
        
        socket.on('video_update', (data) => {
            // Update video feed
            videoFeed.src = 'data:image/jpeg;base64,' + data.frame;
        });
        
        socket.on('mower_status_update', (data) => {
            const status = data.status;
            
            // Update battery level
            const battery = status.battery || 0;
            batteryLevel.style.width = battery + '%';
            batteryPercentage.textContent = battery + '%';
            
            // Update movement status
            movementStatus.textContent = status.moving ? 
                status.direction.charAt(0).toUpperCase() + status.direction.slice(1) + 
                ' (' + status.speed + '%)' : 
                'Stopped';
            
            // Update blade status
            bladeStatus.textContent = status.blade_active ? 
                'Active (' + status.blade_speed + '%)' : 
                'Inactive';
            
            // Update autonomous mode
            autonomousSwitch.checked = status.autonomous_mode || false;
        });
        
        socket.on('obstacle_alert', (data) => {
            // Show obstacle alert
            obstacleAlert.style.display = 'block';
            logMessage('Obstacle detected at ' + data.distance + 'cm', 'warning');
            
            // Hide after 3 seconds
            setTimeout(() => {
                obstacleAlert.style.display = 'none';
            }, 3000);
        });
        
        // Control events
        document.querySelectorAll('.direction-btn').forEach(btn => {
            if (btn.id !== 'blade-toggle') {
                btn.addEventListener('click', () => {
                    const direction = btn.getAttribute('data-direction');
                    const speed = parseInt(speedSlider.value);
                    
                    socket.emit('command', {
                        movement: {
                            direction: direction,
                            speed: speed
                        }
                    });
                    
                    logMessage('Sent command: ' + direction + ' at ' + speed + '%');
                });
            }
        });
        
        bladeToggle.addEventListener('click', () => {
            bladeActive = !bladeActive;
            
            socket.emit('command', {
                blade: {
                    active: bladeActive,
                    speed: 100
                }
            });
            
            bladeToggle.classList.toggle('btn-danger', bladeActive);
            bladeToggle.classList.toggle('btn-secondary', !bladeActive);
            
            logMessage('Blade ' + (bladeActive ? 'activated' : 'deactivated'));
        });
        
        autonomousSwitch.addEventListener('change', () => {
            socket.emit('command', {
                autonomous: autonomousSwitch.checked
            });
            
            logMessage('Autonomous mode ' + (autonomousSwitch.checked ? 'enabled' : 'disabled'));
        });
        
        speedSlider.addEventListener('input', () => {
            speedValue.textContent = speedSlider.value;
        });
        
        snapshotBtn.addEventListener('click', () => {
            fetch('/api/snapshot', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    logMessage('Snapshot saved: ' + data.filename);
                } else {
                    logMessage('Failed to take snapshot: ' + data.error, 'error');
                }
            })
            .catch(error => {
                logMessage('Error taking snapshot: ' + error, 'error');
            });
        });
        
        recordBtn.addEventListener('click', () => {
            if (!isRecording) {
                // Start recording
                fetch('/api/start_recording', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        isRecording = true;
                        recordBtn.textContent = 'Stop Recording';
                        recordBtn.classList.remove('btn-danger');
                        recordBtn.classList.add('btn-warning');
                        logMessage('Recording started');
                    } else {
                        logMessage('Failed to start recording: ' + data.error, 'error');
                    }
                })
                .catch(error => {
                    logMessage('Error starting recording: ' + error, 'error');
                });
            } else {
                // Stop recording
                fetch('/api/stop_recording', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        isRecording = false;
                        recordBtn.textContent = 'Start Recording';
                        recordBtn.classList.remove('btn-warning');
                        recordBtn.classList.add('btn-danger');
                        logMessage('Recording saved: ' + data.filename + ' (' + data.frame_count + ' frames)');
                    } else {
                        logMessage('Failed to stop recording: ' + data.error, 'error');
                    }
                })
                .catch(error => {
                    logMessage('Error stopping recording: ' + error, 'error');
                });
            }
        });
        
        // Helper functions
        function logMessage(message, type = 'info') {
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';
            
            if (type === 'error') {
                logEntry.style.color = '#dc3545';
            } else if (type === 'warning') {
                logEntry.style.color = '#ffc107';
            }
            
            logEntry.textContent = `[${timestamp}] ${message}`;
            logContainer.appendChild(logEntry);
            
            // Scroll to bottom
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    </script>
</body>
</html>""")

# Main function
def main():
    """Main function"""
    # Create templates
    create_templates()
    
    # Create a placeholder image for when no video is available
    os.makedirs('static/images', exist_ok=True)
    placeholder = np.ones((480, 640, 3), dtype=np.uint8) * 100
    cv2.putText(placeholder, "No Video Signal", (180, 240), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.imwrite('static/images/no-video.jpg', placeholder)
    
    # Start heartbeat thread
    thread = threading.Thread(target=heartbeat_thread)
    thread.daemon = True
    thread.start()
    
    # Start the server
    logger.info("Starting server on port 5000")
    socketio.run(app, host='0.0.0.0', port=5000)

if __name__ == "__main__":
    main()