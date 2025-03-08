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

## Project Structure

- **raspberry_pi/**: Code that runs on the Raspberry Pi controller
  - `mower_controller.py`: Main controller for the robot mower
- **server/**: Server code for remote control and monitoring
  - `server.py`: Web server for remote control interface

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

### Raspberry Pi Setup

1. Install the required Python packages:
   ```
   pip install socketio opencv-python numpy picamera2 RPi.GPIO
   ```

2. Configure the Raspberry Pi to run the controller on startup:
   ```
   sudo nano /etc/rc.local
   ```
   Add before the exit line:
   ```
   python3 /path/to/mower_controller.py --server http://your-server-ip:5000 &
   ```

### Server Setup

1. Install the required packages:
   ```
   pip install flask flask-socketio eventlet opencv-python numpy
   ```

2. Run the server:
   ```
   python server.py
   ```

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