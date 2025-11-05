# test_high_ports.py
import cv2
import time

def test_high_ports():
    base_url = "rtsp://admin:admin@10.21.96.111"
    
    # Common high ports for RTSP
    high_ports = [8554, 10554, 1554, 5544, 8555, 9554, 10555, 11554]
    
    # Common RTSP paths to try with each port
    paths = [
        "",
        "/stream1",
        "/cam/realmonitor?channel=1&subtype=0", 
        "/h264",
        "/11",
        "/Streaming/Channels/101",
        "/live/ch00_0"
    ]
    
    working_urls = []
    
    for port in high_ports:
        for path in paths:
            if path and not path.startswith('/'):
                path = '/' + path
                
            url = f"{base_url}:{port}{path}"
            print(f"Testing: {url}")
            
            try:
                cap = cv2.VideoCapture(url)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                
                if cap.isOpened():
                    start_time = time.time()
                    while (time.time() - start_time) < 8:  # 8 second timeout
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            print(f"✅ SUCCESS! Working URL: {url}")
                            working_urls.append(url)
                            cap.release()
                            break
                        time.sleep(0.5)
                    else:
                        print(f"❌ Can open but no frames")
                else:
                    print(f"❌ Cannot open")
                    
                cap.release()
                
            except Exception as e:
                print(f"❌ Error: {e}")
    
    return working_urls

if __name__ == "__main__":
    print("Testing high ports for RTSP...")
    working_urls = test_high_ports()
    
    if working_urls:
        print(f"\n🎉 Found {len(working_urls)} working URLs:")
        for url in working_urls:
            print(f"   {url}")
    else:
        print("\n😞 No working configurations found")
        print("\nNext steps:")
        print("1. Check camera web interface for RTSP port settings")
        print("2. Try accessing http://10.21.96.111 in browser")
        print("3. Look for network/streaming settings")
        print("4. Change RTSP port to 8554 or higher")