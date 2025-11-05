from flask import Flask, render_template, jsonify
import logging
from config import config
from models import cctv_manager
from datetime import datetime
from models.face_matcher import AdvancedFaceMatcher
from models.cctv_manager import CCTVManager

# Import routes
from routes.person_routes import person_bp, init_person_routes
from routes.cctv_routes import cctv_bp, init_cctv_routes
from routes.api_routes import api_bp, init_api_routes

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def create_app(config_name='default'):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Initialize components
    try:
        # MANUAL WORK: These might take time to download models on first run
        logger.info("Initializing Face Matcher...")
        face_matcher = AdvancedFaceMatcher()
        
        logger.info("Initializing CCTV Manager...")
        cctv_manager = CCTVManager(app.config)
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise
    
    # Initialize routes with dependencies
    init_person_routes(app.config, face_matcher)
    init_cctv_routes(app.config, cctv_manager, face_matcher)
    init_api_routes(app.config, cctv_manager)
    
    # Register blueprints
    app.register_blueprint(person_bp)
    app.register_blueprint(cctv_bp)
    app.register_blueprint(api_bp)
    
    # Add this to your app.py after CCTV manager initialization
    def add_test_streams():
        """Add public test streams for demonstration"""
        test_streams = [
            {
                "name": "Test Stream 1", 
                "url": "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov",
                "location": "Public Test"
            },
            {
                "name": "Test Stream 2",
                "url": "rtsp://184.72.239.149/vod/mp4:BigBuckBunny_175k.mov", 
                "location": "Public Test"
            }
        ]
        
        for stream in test_streams:
            try:
                cctv_manager.add_stream(stream["name"], stream["url"], stream["location"])
                logger.info(f"Added test stream: {stream['name']}")
            except Exception as e:
                logger.warning(f"Failed to add test stream {stream['name']}: {e}")

    # Call this function after CCTV manager is initialized
    add_test_streams()
    
    # Root route
    @app.route('/')
    def index():
        return render_template('dashboard.html')
    
    # Error handlers
        # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return """
        <html>
            <head><title>404 - Page Not Found</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1>404 - Page Not Found</h1>
                <p>The page you are looking for doesn't exist.</p>
                <a href="/">Go to Dashboard</a>
            </body>
        </html>
        """, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    logger.info("Missing Person Detection System initialized successfully")
    return app

if __name__ == '__main__':
    # MANUAL WORK: 
    # 1. First run might download AI models (can take several minutes)
    # 2. Make sure you have proper RTSP URLs for CCTV cameras
    # 3. Ensure all directories are created properly
    
    app = create_app()
    
    print("\n" + "="*50)
    print("MISSING PERSON DETECTION SYSTEM")
    print("="*50)
    print("Access the application at: http://localhost:8001")
    print("Available pages:")
    print("  - Dashboard: /")
    print("  - Add Person: /person/upload")
    print("  - CCTV Management: /cctv/management")
    print("="*50 + "\n")
    
    
    
    # Add webcam stream for testing
    #cctv_manager.add_webcam_stream("Test Webcam", "Local Computer")
    # Add this right after the line you commented out:
    try:
        # Create a simple test stream manually
        import numpy as np
        import cv2
        from queue import Queue
        
        # Create a test image
        test_image = np.ones((480, 640, 3), dtype=np.uint8) * 255  # White background
        cv2.putText(test_image, "Face Detection System", (50, 150), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        cv2.putText(test_image, "Demo Mode - Working", (50, 200), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.putText(test_image, "Add CCTV streams to test", (50, 250), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # Manually add to CCTV manager
        cctv_manager.active_streams["Demo Stream"] = {
            'url': 'demo',
            'location': 'Demo Location',
            'active': True,
            'last_frame': test_image,
            'last_update': datetime.now(),
            'added_date': datetime.now().isoformat(),
            'error_count': 0
        }
        cctv_manager.frame_queues["Demo Stream"] = Queue(maxsize=1)
        cctv_manager.frame_queues["Demo Stream"].put(test_image)
        
        logger.info("Added demo stream for testing")
        
    except Exception as e:
        logger.error(f"Failed to add demo stream: {e}")
    app.run(
        host='0.0.0.0', 
        port=8001, 
        debug=True,
        threaded=True  # Important for handling multiple CCTV streams
    )
    
    