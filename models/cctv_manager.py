import cv2
import threading
import time
import logging
import json
import base64
import cv2
import numpy as np
import time

import os
from datetime import datetime
from queue import Queue
import numpy as np

logger = logging.getLogger(__name__)

class CCTVManager:
    def __init__(self, config):
        self.config = config
        self.active_streams = {}
        self.frame_queues = {}
        self.stream_threads = {}
        self.running = False
        
        # Load existing streams from database
        self.load_streams_from_db()
        logger.info("CCTV Manager initialized successfully")
    
    def load_streams_from_db(self):
        """Load CCTV streams from database file"""
        try:
            if not hasattr(self.config, 'CCTV_DB_FILE'):
                logger.info("No CCTV_DB_FILE in config, starting fresh")
                return
                
            if not os.path.exists(self.config.CCTV_DB_FILE):
                logger.info("No CCTV database file found, starting fresh")
                return
                
            with open(self.config.CCTV_DB_FILE, 'r') as f:
                content = f.read().strip()
                if not content:
                    logger.info("CCTV database file is empty")
                    return
                    
                streams_data = json.loads(content)
                    
            for stream_name, stream_info in streams_data.items():
                self.add_stream(
                    stream_name,
                    stream_info['url'],
                    stream_info['location'],
                    start_monitoring=False
                )
                
            logger.info(f"Loaded {len(streams_data)} streams from database")
        except Exception as e:
            logger.error(f"Error loading CCTV database: {e}")
    
    def save_streams_to_db(self):
        """Save CCTV streams to database file"""
        try:
            if not hasattr(self.config, 'CCTV_DB_FILE'):
                return
                
            streams_data = {}
            for stream_name, stream_info in self.active_streams.items():
                streams_data[stream_name] = {
                    'url': stream_info['url'],
                    'location': stream_info['location'],
                    'added_date': stream_info.get('added_date', datetime.now().isoformat())
                }
            
            with open(self.config.CCTV_DB_FILE, 'w') as f:
                json.dump(streams_data, f, indent=2)
                
            logger.info(f"Saved {len(streams_data)} streams to database")
        except Exception as e:
            logger.error(f"Error saving CCTV database: {e}")
    
    def add_stream(self, stream_name, rtsp_url, location, start_monitoring=True):
        """Add a new RTSP stream"""
        logger.info(f"Attempting to add stream: {stream_name}")
        
        if stream_name in self.active_streams:
            logger.warning(f"Stream {stream_name} already exists")
            return False
        
        # Test connection first (skip for webcam and demo)
        if rtsp_url not in ["0", "demo"] and not self.test_rtsp_connection(rtsp_url):
            logger.error(f"Failed to connect to RTSP stream: {rtsp_url}")
            return False
        
        self.active_streams[stream_name] = {
            'url': rtsp_url,
            'location': location,
            'active': True,
            'last_frame': None,
            'last_update': None,
            'added_date': datetime.now().isoformat(),
            'error_count': 0
        }
        
        # Create frame queue for this stream
        self.frame_queues[stream_name] = Queue(maxsize=1)
        
        if start_monitoring:
            self.start_stream_monitoring(stream_name)
        
        # Save to database
        self.save_streams_to_db()
        
        logger.info(f"Successfully added stream: {stream_name} at location: {location}")
        return True
    
    def add_webcam_stream(self, stream_name="Live Webcam", location="Your Location"):
        """Add webcam as a stream for testing"""
        logger.info(f"Attempting to add webcam stream: {stream_name}")

        webcam_url = "0"

        # ✅ Fix: Remove existing webcam stream if already present
        if stream_name in self.active_streams:
            logger.warning(f"Stream {stream_name} already exists — removing and reinitializing.")
            try:
                del self.active_streams[stream_name]
                logger.info(f"Removed old stream entry for {stream_name}.")
            except Exception as e:
                logger.error(f"Failed to remove old webcam stream: {e}")

        # Test if webcam is available
        try:
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    logger.info(f"Webcam is available, adding stream: {stream_name}")
                    return self.add_stream(stream_name, webcam_url, location)
                else:
                    logger.error("Webcam opened but cannot read frames")
            else:
                logger.error("Webcam not accessible or already in use.")
        except Exception as e:
            logger.error(f"Error testing webcam: {e}")

        logger.error("Failed to add webcam stream — switching to demo.")
        return False

    
    def test_rtsp_connection(self, rtsp_url):
        """Test if RTSP stream is accessible"""
        try:
            logger.info(f"Testing RTSP connection: {rtsp_url}")
            cap = cv2.VideoCapture(rtsp_url)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
            
            if not cap.isOpened():
                return False
            
            # Try to read a frame with timeout
            start_time = time.time()
            while (time.time() - start_time) < 10:
                ret, frame = cap.read()
                if ret and frame is not None:
                    cap.release()
                    return True
                time.sleep(0.1)
            
            cap.release()
            return False
            
        except Exception as e:
            logger.error(f"RTSP connection test failed for {rtsp_url}: {e}")
            return False
    
    def start_stream_monitoring(self, stream_name):
        """Start monitoring a specific stream"""
        if stream_name not in self.active_streams:
            logger.error(f"Stream {stream_name} not found")
            return False
        
        if stream_name in self.stream_threads and self.stream_threads[stream_name].is_alive():
            logger.warning(f"Stream {stream_name} is already being monitored")
            return True
        
        # Start monitoring thread
        self.running = True
        thread = threading.Thread(
            target=self._monitor_stream,
            args=(stream_name,),
            daemon=True
        )
        thread.start()
        self.stream_threads[stream_name] = thread
        
        logger.info(f"Started monitoring stream: {stream_name}")
        return True
    
    def _monitor_stream(self, stream_name):
        """Monitor stream and capture frames with webcam support"""
        stream_info = self.active_streams[stream_name]
        
        # Initialize webcam if this is a webcam stream
        cap = None
        if stream_info['url'] == "0":
            try:
                cap = cv2.VideoCapture(0)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 15)
                logger.info(f"Webcam initialized for {stream_name}")
            except Exception as e:
                logger.error(f"Failed to initialize webcam: {e}")
                return
        
        while self.running and stream_info['active']:
            try:
                if stream_info['url'] == "0" and cap is not None:
                    # Read from webcam
                    ret, frame = cap.read()
                    if not ret:
                        logger.warning("Failed to read from webcam")
                        time.sleep(1)
                        continue
                    # Resize for consistency
                    frame = cv2.resize(frame, (640, 480))
                else:
                    # Create demo frame for non-webcam streams
                    frame = np.ones((480, 640, 3), dtype=np.uint8) * 255
                    cv2.putText(frame, f"Stream: {stream_name}", (50, 150), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
                    cv2.putText(frame, "Face Detection System", (50, 200), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                    cv2.putText(frame, "Look at webcam for face detection", (50, 250), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                    cv2.putText(frame, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), (50, 300), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                
                # Update stream info
                stream_info['last_frame'] = frame
                stream_info['last_update'] = datetime.now()
                
                # Put frame in queue
                if not self.frame_queues[stream_name].empty():
                    try:
                        self.frame_queues[stream_name].get_nowait()
                    except:
                        pass
                
                self.frame_queues[stream_name].put(frame)
                
                time.sleep(0.1)  # 10 FPS for smooth video
                
            except Exception as e:
                logger.error(f"Error in stream monitoring for {stream_name}: {e}")
                time.sleep(1)
        
        # Release webcam when done
        if cap is not None:
            cap.release()
            logger.info(f"Webcam released for {stream_name}")
    
    def get_current_frame(self, stream_name):
        """Return the latest frame for a given stream, using queue fallback and safe placeholder"""
        try:
            if stream_name not in self.active_streams:
                logger.warning(f"Unknown stream requested: {stream_name}")
                return None

            frame = None
            # Try from queue
            if stream_name in self.frame_queues and not self.frame_queues[stream_name].empty():
                try:
                    frame = self.frame_queues[stream_name].get_nowait()
                    self.active_streams[stream_name]["last_frame"] = frame
                except Exception:
                    pass
            else:
                # fallback
                frame = self.active_streams[stream_name].get("last_frame")

            # Graceful startup placeholder
            if frame is None:
                placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(placeholder, "Initializing Webcam...", (100, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
                cv2.putText(placeholder, time.strftime("%H:%M:%S"), (240, 300),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
                ret, buffer = cv2.imencode(".jpg", placeholder)
                return buffer.tobytes()

            # Encode real frame
            ret, buffer = cv2.imencode(".jpg", frame)
            if not ret:
                logger.error(f"Frame encoding failed for {stream_name}")
                return None

            return buffer.tobytes()

        except Exception as e:
            logger.error(f"Error retrieving current frame for {stream_name}: {e}")
            return None


    
    def get_stream_status(self):
        """Get status of all streams"""
        status = {}
        for stream_name, stream_info in self.active_streams.items():
            status[stream_name] = {
                'location': stream_info['location'],
                'active': stream_info['active'],
                'last_update': stream_info['last_update'],
                'error_count': stream_info['error_count'],
                'url': stream_info['url']
            }
        return status
    
    def stop_all_streams(self):
        """Stop all stream monitoring"""
        self.running = False
        for thread in self.stream_threads.values():
            thread.join(timeout=5)
        
        logger.info("All stream monitoring stopped")