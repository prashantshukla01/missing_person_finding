# check_cctv_manager.py
import inspect
from models.cctv_manager import CCTVManager

print("CCTVManager methods:")
methods = [method for method in dir(CCTVManager) if not method.startswith('_')]
for method in methods:
    print(f" - {method}")

print(f"\nTotal methods: {len(methods)}")

# Check if specific methods exist
required_methods = ['add_webcam_stream', 'add_stream', 'get_current_frame']
for method in required_methods:
    if hasattr(CCTVManager, method):
        print(f"✅ {method} exists")
    else:
        print(f"❌ {method} missing")