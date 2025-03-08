# Autonomous Robot Mower

An autonomous robot lawn mower project using Raspberry Pi 5 with Hailo AI HAT for intelligent navigation and obstacle detection.

## Project Overview

This project implements a fully autonomous robot lawn mower that can be controlled remotely or operate autonomously. It uses computer vision and AI for navigation, obstacle detection, and efficient mowing patterns.

### Features

- **Autonomous Operation**: Implements intelligent mowing patterns
- **Obstacle Detection**: Uses ultrasonic sensors and computer vision
- **Remote Control**: Web-based interface for manual control
- **Live Video Feed**: Streams video with object detection overlay
- **Safety Features**: Automatic shutdown on connection loss or obstacles
- **AI-Powered Navigation**: Uses Hailo AI HAT for efficient path planning

## System Architecture

This project uses a distributed architecture with two main components:

- **Raspberry Pi Controller**: Runs directly on the robot mower
  - Located in the `raspberry_pi/` directory
  - `mower_controller.py`: Main controller that handles autonomous operation, sensors, motors, and camera
  - Connects to the control server over WiFi/network
  - Operates independently when connection is lost

- **Ubuntu Control Server**: Runs on a separate Ubuntu server on the same network
  - Located in the `server/` directory
  - `server.py`: Web-based control panel for monitoring and manual control
  - Provides real-time video streaming and telemetry
  - Allows remote operation from any device with a web browser

## Hardware Requirements

- Raspberry Pi 5
- Hailo AI HAT (or compatible AI accelerator)
- Motor controller board
- DC motors for drive and cutting blade
- Ultrasonic distance sensors
- Camera module
- Battery power system
- Chassis and mechanical components

## Software Setup

### Raspberry Pi Setup (On the mower)

1. Install the required Python packages on the Raspberry Pi:
   ```
   pip install socketio opencv-python numpy picamera2 RPi.GPIO
   ```

2. Configure the Raspberry Pi to run the controller on startup:
   ```
   sudo nano /etc/rc.local
   ```
   Add before the exit line:
   ```
   python3 /path/to/raspberry_pi/mower_controller.py --server http://ubuntu-server-ip:5000 &
   ```

3. Make sure the Raspberry Pi connects to the same network as your Ubuntu server

### Ubuntu Server Setup (Control panel)

1. Install the required packages on your Ubuntu server:
   ```
   pip install flask flask-socketio eventlet opencv-python numpy
   ```

2. Run the control panel server:
   ```
   python server/server.py
   ```

3. Access the control panel by navigating to `http://ubuntu-server-ip:5000` in your web browser

## Usage

### Autonomous Mode

In autonomous mode, the mower will:
1. Navigate in a systematic pattern
2. Detect and avoid obstacles
3. Return to base when battery is low

### Manual Control

Access the web interface at `http://your-server-ip:5000` to:
- View live video feed
- Control movement direction
- Activate/deactivate cutting blade
- Toggle autonomous mode
- Monitor battery and sensor status

## Development

This project is under active development. Planned features include:
- GPS integration for precise navigation
- Improved AI for grass detection and cutting height adjustment
- Mobile app for remote control
- Weather-aware scheduling

## License

MIT License