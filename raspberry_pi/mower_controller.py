#!/usr/bin/env python3
"""
Robot Mower Controller for Raspberry Pi 5 with Hailo AI HAT
"""
import time
import json
import cv2
import numpy as np
import socketio
import threading
import argparse
import logging
from datetime import datetime
import RPi.GPIO as GPIO
from picamera2 import Picamera2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mower_controller.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MowerController")

# Motor control pins
LEFT_MOTOR_ENABLE = 17
LEFT_MOTOR_FWD = 27
LEFT_MOTOR_REV = 22
RIGHT_MOTOR_ENABLE = 23
RIGHT_MOTOR_FWD = 24
RIGHT_MOTOR_REV = 25

# Blade motor control
BLADE_MOTOR_ENABLE = 5
BLADE_MOTOR_PWM = 6

# Ultrasonic sensor pins
TRIG_PIN = 16
ECHO_PIN = 20

# Status LEDs
STATUS_LED_GREEN = 12
STATUS_LED_RED = 13

class HailoAI:
    """Interface with Hailo AI HAT for object detection and navigation"""
    
    def __init__(self):
        logger.info("Initializing Hailo AI HAT")
        # This is a placeholder for actual Hailo AI HAT initialization
        # You would need to use the specific Hailo SDK for your model
        self.initialized = False
        try:
            # Import Hailo SDK
            # from hailo_platform import HailoInference
            # self.hailo = HailoInference()
            # self.hailo.init()
            # self.initialized = True
            
            # For now, we'll simulate the Hailo AI HAT
            self.initialized = True
            logger.info("Hailo AI HAT initialized (simulated)")
        except Exception as e:
            logger.error(f"Failed to initialize Hailo AI HAT: {e}")
    
    def process_frame(self, frame):
        """Process a frame with the Hailo AI for object detection"""
        if not self.initialized:
            return frame, []
        
        # Placeholder for actual Hailo AI processing
        # In a real implementation, you would:
        # 1. Preprocess the frame for the Hailo model
        # 2. Run inference on the Hailo hardware
        # 3. Process the results
        
        # For simulation, we'll just detect simple colored objects
        objects = []
        
        # Convert to HSV for color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Define color ranges (example: detect red objects as obstacles)
        lower_red = np.array([0, 120, 70])
        upper_red = np.array([10, 255, 255])
        mask = cv2.inRange(hsv, lower_red, upper_red)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            if cv2.contourArea(contour) > 500:  # Filter small contours
                x, y, w, h = cv2.boundingRect(contour)
                objects.append({
                    'type': 'obstacle',
                    'confidence': 0.95,
                    'bbox': [x, y, x+w, y+h]
                })
                # Draw bounding box on frame
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
        
        return frame, objects

class MotorController:
    """Control the motors of the robot mower"""
    
    def __init__(self):
        logger.info("Initializing motor controller")
        # Set up GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Set up motor pins
        for pin in [LEFT_MOTOR_ENABLE, LEFT_MOTOR_FWD, LEFT_MOTOR_REV,
                   RIGHT_MOTOR_ENABLE, RIGHT_MOTOR_FWD, RIGHT_MOTOR_REV,
                   BLADE_MOTOR_ENABLE, BLADE_MOTOR_PWM,
                   STATUS_LED_GREEN, STATUS_LED_RED]:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        
        # Set up PWM for motor speed control
        self.left_pwm = GPIO.PWM(LEFT_MOTOR_ENABLE, 100)
        self.right_pwm = GPIO.PWM(RIGHT_MOTOR_ENABLE, 100)
        self.blade_pwm = GPIO.PWM(BLADE_MOTOR_PWM, 100)
        
        self.left_pwm.start(0)
        self.right_pwm.start(0)
        self.blade_pwm.start(0)
        
        # Set up ultrasonic sensor
        GPIO.setup(TRIG_PIN, GPIO.OUT)
        GPIO.setup(ECHO_PIN, GPIO.IN)
        
        # Initialize status
        self.status = {
            'moving': False,
            'direction': 'stopped',
            'blade_active': False,
            'speed': 0,
            'blade_speed': 0,
            'battery': 100,  # Simulated battery level
            'obstacles_detected': False
        }
        
        # Turn on green LED to indicate ready
        GPIO.output(STATUS_LED_GREEN, GPIO.HIGH)
    
    def move(self, direction, speed=50):
        """
        Move the mower in the specified direction
        direction: 'forward', 'backward', 'left', 'right', 'stop'
        speed: 0-100 percentage
        """
        # Clamp speed to valid range
        speed = max(0, min(100, speed))
        
        # Update status
        self.status['moving'] = direction != 'stop'
        self.status['direction'] = direction
        self.status['speed'] = speed
        
        # Stop all motors first
        GPIO.output(LEFT_MOTOR_FWD, GPIO.LOW)
        GPIO.output(LEFT_MOTOR_REV, GPIO.LOW)
        GPIO.output(RIGHT_MOTOR_FWD, GPIO.LOW)
        GPIO.output(RIGHT_MOTOR_REV, GPIO.LOW)
        
        if direction == 'forward':
            GPIO.output(LEFT_MOTOR_FWD, GPIO.HIGH)
            GPIO.output(RIGHT_MOTOR_FWD, GPIO.HIGH)
            self.left_pwm.ChangeDutyCycle(speed)
            self.right_pwm.ChangeDutyCycle(speed)
        
        elif direction == 'backward':
            GPIO.output(LEFT_MOTOR_REV, GPIO.HIGH)
            GPIO.output(RIGHT_MOTOR_REV, GPIO.HIGH)
            self.left_pwm.ChangeDutyCycle(speed)
            self.right_pwm.ChangeDutyCycle(speed)
        
        elif direction == 'left':
            GPIO.output(LEFT_MOTOR_REV, GPIO.HIGH)
            GPIO.output(RIGHT_MOTOR_FWD, GPIO.HIGH)
            self.left_pwm.ChangeDutyCycle(speed)
            self.right_pwm.ChangeDutyCycle(speed)
        
        elif direction == 'right':
            GPIO.output(LEFT_MOTOR_FWD, GPIO.HIGH)
            GPIO.output(RIGHT_MOTOR_REV, GPIO.HIGH)
            self.left_pwm.ChangeDutyCycle(speed)
            self.right_pwm.ChangeDutyCycle(speed)
        
        elif direction == 'stop':
            self.left_pwm.ChangeDutyCycle(0)
            self.right_pwm.ChangeDutyCycle(0)
        
        logger.info(f"Moving {direction} at speed {speed}")
    
    def control_blade(self, active, speed=100):
        """Control the cutting blade"""
        # Clamp speed to valid range
        speed = max(0, min(100, speed))
        
        # Update status
        self.status['blade_active'] = active
        self.status['blade_speed'] = speed if active else 0
        
        if active:
            GPIO.output(BLADE_MOTOR_ENABLE, GPIO.HIGH)
            self.blade_pwm.ChangeDutyCycle(speed)
            logger.info(f"Blade activated at speed {speed}")
        else:
            GPIO.output(BLADE_MOTOR_ENABLE, GPIO.LOW)
            self.blade_pwm.ChangeDutyCycle(0)
            logger.info("Blade deactivated")
    
    def measure_distance(self):
        """Measure distance with ultrasonic sensor"""
        # Send trigger pulse
        GPIO.output(TRIG_PIN, GPIO.HIGH)
        time.sleep(0.00001)  # 10 microseconds
        GPIO.output(TRIG_PIN, GPIO.LOW)
        
        # Wait for echo to start
        pulse_start = time.time()
        timeout = pulse_start + 0.1  # 100ms timeout
        
        while GPIO.input(ECHO_PIN) == 0:
            pulse_start = time.time()
            if pulse_start > timeout:
                return 400  # Return max distance if timeout
        
        # Wait for echo to end
        pulse_end = time.time()
        timeout = pulse_end + 0.1  # 100ms timeout
        
        while GPIO.input(ECHO_PIN) == 1:
            pulse_end = time.time()
            if pulse_end > timeout:
                return 400  # Return max distance if timeout
        
        # Calculate distance
        pulse_duration = pulse_end - pulse_start
        distance = pulse_duration * 17150  # Speed of sound in cm/s
        
        return round(distance, 2)
    
    def check_obstacles(self):
        """Check for obstacles using ultrasonic sensor"""
        distance = self.measure_distance()
        
        # If obstacle is closer than 30cm, consider it detected
        obstacles_detected = distance < 30
        self.status['obstacles_detected'] = obstacles_detected
        
        if obstacles_detected:
            # Turn on red LED to indicate obstacle
            GPIO.output(STATUS_LED_RED, GPIO.HIGH)
            logger.warning(f"Obstacle detected at {distance}cm")
        else:
            GPIO.output(STATUS_LED_RED, GPIO.LOW)
        
        return obstacles_detected, distance
    
    def get_status(self):
        """Get the current status of the mower"""
        # Simulate battery discharge
        if self.status['moving'] or self.status['blade_active']:
            self.status['battery'] = max(0, self.status['battery'] - 0.01)
        
        return self.status
    
    def cleanup(self):
        """Clean up GPIO pins"""
        self.move('stop')
        self.control_blade(False)
        GPIO.output(STATUS_LED_GREEN, GPIO.LOW)
        GPIO.output(STATUS_LED_RED, GPIO.LOW)
        GPIO.cleanup()
        logger.info("Motor controller cleaned up")

class MowerController:
    """Main controller for the robot mower"""
    
    def __init__(self, server_url):
        logger.info(f"Initializing mower controller, connecting to {server_url}")
        self.server_url = server_url
        self.motors = MotorController()
        self.hailo_ai = HailoAI()
        
        # Initialize camera
        self.camera = Picamera2()
        self.camera.configure(self.camera.create_preview_configuration(
            main={"size": (640, 480)},
            lores={"size": (320, 240), "format": "YUV420"}
        ))
        self.camera.start()
        time.sleep(2)  # Allow camera to warm up
        
        # Initialize Socket.IO client
        self.sio = socketio.Client()
        self.setup_socketio()
        
        # Start threads
        self.running = True
        self.threads = []
        
        # Status variables
        self.autonomous_mode = False
        self.last_command_time = time.time()
        self.last_heartbeat = time.time()
    
    def setup_socketio(self):
        """Set up Socket.IO event handlers"""
        @self.sio.event
        def connect():
            logger.info("Connected to control server")
            self.sio.emit('mower_status', self.motors.get_status())
        
        @self.sio.event
        def disconnect():
            logger.warning("Disconnected from control server")
            # Stop the mower when connection is lost
            self.motors.move('stop')
            self.motors.control_blade(False)
        
        @self.sio.event
        def command(data):
            logger.info(f"Received command: {data}")
            self.last_command_time = time.time()
            
            if 'movement' in data:
                direction = data['movement']['direction']
                speed = data['movement'].get('speed', 50)
                self.motors.move(direction, speed)
            
            if 'blade' in data:
                active = data['blade']['active']
                speed = data['blade'].get('speed', 100)
                self.motors.control_blade(active, speed)
            
            if 'autonomous' in data:
                self.autonomous_mode = data['autonomous']
                logger.info(f"Autonomous mode: {self.autonomous_mode}")
                
                if not self.autonomous_mode:
                    # Stop when exiting autonomous mode
                    self.motors.move('stop')
        
        @self.sio.event
        def heartbeat(data):
            self.last_heartbeat = time.time()
            self.sio.emit('mower_status', self.motors.get_status())
    
    def connect_to_server(self):
        """Connect to the control server"""
        try:
            self.sio.connect(self.server_url)
            logger.info(f"Connected to server at {self.server_url}")
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False
        return True
    
    def start(self):
        """Start the mower controller threads"""
        # Connect to server
        if not self.connect_to_server():
            logger.error("Failed to start mower controller")
            return False
        
        # Start video streaming thread
        video_thread = threading.Thread(target=self.video_stream_loop)
        video_thread.daemon = True
        video_thread.start()
        self.threads.append(video_thread)
        
        # Start obstacle detection thread
        obstacle_thread = threading.Thread(target=self.obstacle_detection_loop)
        obstacle_thread.daemon = True
        obstacle_thread.start()
        self.threads.append(obstacle_thread)
        
        # Start autonomous control thread
        autonomous_thread = threading.Thread(target=self.autonomous_control_loop)
        autonomous_thread.daemon = True
        autonomous_thread.start()
        self.threads.append(autonomous_thread)
        
        # Start watchdog thread
        watchdog_thread = threading.Thread(target=self.watchdog_loop)
        watchdog_thread.daemon = True
        watchdog_thread.start()
        self.threads.append(watchdog_thread)
        
        logger.info("Mower controller started")
        return True
    
    def video_stream_loop(self):
        """Capture video and stream to server"""
        logger.info("Starting video stream loop")
        
        while self.running:
            try:
                # Capture frame
                frame = self.camera.capture_array()
                
                # Process with Hailo AI
                processed_frame, objects = self.hailo_ai.process_frame(frame)
                
                # Add timestamp to frame
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(processed_frame, timestamp, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Convert to JPEG
                _, jpeg = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                
                # Send to server
                if self.sio.connected:
                    self.sio.emit('video_frame', {
                        'frame': jpeg.tobytes(),
                        'objects': objects,
                        'timestamp': timestamp
                    })
                
                # Sleep to control frame rate (10 FPS)
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in video stream: {e}")
                time.sleep(1)
    
    def obstacle_detection_loop(self):
        """Continuously check for obstacles"""
        logger.info("Starting obstacle detection loop")
        
        while self.running:
            try:
                # Check for obstacles
                obstacle_detected, distance = self.motors.check_obstacles()
                
                # If obstacle detected and mower is moving forward, stop
                if obstacle_detected and self.motors.status['direction'] == 'forward':
                    logger.warning(f"Obstacle detected at {distance}cm, stopping")
                    self.motors.move('stop')
                    
                    # Notify server
                    if self.sio.connected:
                        self.sio.emit('obstacle_detected', {
                            'distance': distance,
                            'timestamp': datetime.now().isoformat()
                        })
                
                # Sleep to control detection rate
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error in obstacle detection: {e}")
                time.sleep(1)
    
    def autonomous_control_loop(self):
        """Autonomous control logic"""
        logger.info("Starting autonomous control loop")
        
        # Simple lawn mowing pattern variables
        current_direction = 'forward'
        turn_direction = 'right'
        forward_time = 0
        
        while self.running:
            try:
                if self.autonomous_mode:
                    # Get current status
                    status = self.motors.get_status()
                    
                    # If obstacle detected, change direction
                    if status['obstacles_detected']:
                        logger.info("Obstacle detected in autonomous mode, changing direction")
                        
                        # Back up slightly
                        self.motors.move('backward', 40)
                        time.sleep(1.5)
                        
                        # Turn to avoid obstacle
                        self.motors.move(turn_direction, 40)
                        time.sleep(2)
                        
                        # Continue forward
                        self.motors.move('forward', 50)
                        forward_time = time.time()
                    
                    # If we've been going forward for a while, make a turn to create a pattern
                    elif current_direction == 'forward' and time.time() - forward_time > 10:
                        logger.info("Changing direction in autonomous pattern")
                        
                        # Stop briefly
                        self.motors.move('stop')
                        time.sleep(0.5)
                        
                        # Turn
                        self.motors.move(turn_direction, 40)
                        time.sleep(1.5)
                        
                        # Alternate turn direction for next time
                        turn_direction = 'left' if turn_direction == 'right' else 'right'
                        
                        # Continue forward
                        self.motors.move('forward', 50)
                        forward_time = time.time()
                    
                    # If we're not moving, start moving
                    elif not status['moving']:
                        logger.info("Starting autonomous movement")
                        self.motors.move('forward', 50)
                        self.motors.control_blade(True, 80)
                        forward_time = time.time()
                        current_direction = 'forward'
                
                # Sleep to control loop rate
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in autonomous control: {e}")
                time.sleep(1)
    
    def watchdog_loop(self):
        """Watchdog to ensure safety if connection is lost"""
        logger.info("Starting watchdog loop")
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check if we've lost connection to the server
                if current_time - self.last_heartbeat > 10:  # 10 seconds timeout
                    logger.warning("Lost connection to server, stopping mower")
                    self.motors.move('stop')
                    self.motors.control_blade(False)
                    
                    # Try to reconnect
                    if not self.sio.connected:
                        try:
                            self.sio.connect(self.server_url)
                        except Exception as e:
                            logger.error(f"Failed to reconnect: {e}")
                
                # Sleep to control watchdog rate
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in watchdog: {e}")
                time.sleep(1)
    
    def stop(self):
        """Stop the mower controller"""
        logger.info("Stopping mower controller")
        self.running = False
        
        # Stop motors
        self.motors.move('stop')
        self.motors.control_blade(False)
        
        # Disconnect from server
        if self.sio.connected:
            self.sio.disconnect()
        
        # Stop camera
        self.camera.stop()
        
        # Clean up GPIO
        self.motors.cleanup()
        
        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=1)
        
        logger.info("Mower controller stopped")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Robot Mower Controller')
    parser.add_argument('--server', type=str, default='http://192.168.1.100:5000',
                       help='URL of the control server')
    args = parser.parse_args()
    
    # Create and start the mower controller
    controller = MowerController(args.server)
    
    try:
        if controller.start():
            # Keep the main thread alive
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping")
    finally:
        controller.stop()

if __name__ == "__main__":
    main()