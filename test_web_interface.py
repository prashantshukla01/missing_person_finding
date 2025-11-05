# test_http_streams.py
import cv2

def test_http_streams():
    http_urls = [
        # MJPEG streams
        "http://10.21.96.111/video",
        "http://10.21.96.111/mjpeg",
        "http://10.21.96.111/cgi-bin/mjpg/video.cgi",
        "http://10.21.96.111:8080/video",
        "http://10.21.96.111:8080/mjpeg",
        
        # H264 streams  
        "http://10.21.96.111/h264",
        "http://10.21.96.111:8080/h264",
        
        # Common paths
        "http://10.21.96.111/stream",
        "http://10.21.96.111:8080/stream",
        "http://10.21.96.111/cam",
        "http://10.21.96.111:8080/cam",
    ]
    
    for url in http_urls:
        print(f"Testing: {url}")
        try:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"✅ SUCCESS! HTTP stream: {url}")
                    cap.release()
                    return url
            cap.release()
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return None

if __name__ == "__main__":
    print("Testing HTTP streaming...")
    stream_url = test_http_streams()
    if stream_url:
        print(f"🎉 Use this URL: {stream_url}")