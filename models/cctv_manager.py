import cv2
import threading
import time
import logging
import json
import base64
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
        if stream_name in self.active_streams:
            logger.warning(f"Stream {stream_name} already exists")
            return False
        
        # Test connection first (skip for webcam)
        if rtsp_url != "0" and not self.test_rtsp_connection(rtsp_url):
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
        
        logger.info(f"Added stream: {stream_name} at location: {location}")
        return True
    
    def add_webcam_stream(self, stream_name="Webcam", location="Local"):
        """Add webcam as a stream for testing"""
        # Use 0 for default webcam
        webcam_url = "0"
        
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
                logger.error("Webcam cannot be opened")
        except Exception as e:
            logger.error(f"Error testing webcam: {e}")
        
        return False
    
    def test_rtsp_connection(self, rtsp_url):
        """Test if RTSP stream is accessible"""
        try:
            # Skip test for webcam
            if rtsp_url == "0":
                return True
                
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
        """Monitor RTSP stream and capture frames"""
        stream_info = self.active_streams[stream_name]
        reconnect_attempts = 0
        max_reconnect_attempts = 5
        
        while self.running and stream_info['active'] and reconnect_attempts < max_reconnect_attempts:
            try:
                # Handle webcam vs RTSP URLs
                if stream_info['url'] == "0":
                    # This is a webcam
                    cap = cv2.VideoCapture(0)
                    logger.info(f"Opening webcam for stream: {stream_name}")
                else:
                    # This is an RTSP URL
                    cap = cv2.VideoCapture(stream_info['url'])
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                
                # Common configuration for both
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, 15)
                
                if cap.isOpened():
                    logger.info(f"Connected to stream: {stream_name}")
                    
                    while self.running and stream_info['active']:
                        ret, frame = cap.read()
                        
                        if ret and frame is not None:
                            # Resize frame for better performance
                            frame = cv2.resize(frame, (640, 480))
                            
                            # Update stream info
                            stream_info['last_frame'] = frame
                            stream_info['last_update'] = datetime.now()
                            stream_info['error_count'] = 0
                            reconnect_attempts = 0
                            
                            # Put frame in queue (replace if full)
                            if not self.frame_queues[stream_name].empty():
                                try:
                                    self.frame_queues[stream_name].get_nowait()
                                except:
                                    pass
                            
                            self.frame_queues[stream_name].put(frame)
                        
                        else:
                            stream_info['error_count'] += 1
                            logger.warning(f"Failed to read frame from {stream_name}, error count: {stream_info['error_count']}")
                            
                            if stream_info['error_count'] > 10:
                                logger.error(f"Too many errors for {stream_name}, attempting reconnect")
                                break
                        
                        time.sleep(0.1)
                    
                    cap.release()
                else:
                    logger.error(f"Failed to open stream: {stream_name}")
                
                reconnect_attempts += 1
                
                if reconnect_attempts < max_reconnect_attempts:
                    logger.info(f"Reconnecting to {stream_name} in 5 seconds... (attempt {reconnect_attempts})")
                    time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in stream monitoring for {stream_name}: {e}")
                reconnect_attempts += 1
                time.sleep(5)
        
        if reconnect_attempts >= max_reconnect_attempts:
            logger.error(f"Max reconnection attempts reached for {stream_name}, marking as inactive")
            stream_info['active'] = False
    
    def get_current_frame(self, stream_name, as_base64=False):
        """Get current frame from stream"""
        if stream_name not in self.frame_queues:
            return None
        
        try:
            frame = self.frame_queues[stream_name].get_nowait()
            
            if as_base64 and frame is not None:
                # Convert frame to base64 for web display
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                return frame_base64
            
            return frame
            
        except:
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