"""Raspberry Pi Face Recognition Treasure Box
Mjpg-Streamer Camera Capture Device
Copyright 2013 Tony DiCola

Mjpg-Streamer device capture class using OpenCV. This class allows you to capture
images from an mjpg-streamer HTTP stream, as if it were a snapshot camera.

This is useful when running the code on a system where the camera is accessed
through mjpg-streamer instead of direct USB access.
"""
import threading
import time
import cv2
import requests
from requests.auth import HTTPBasicAuth
import numpy as np
from io import BytesIO

# Rate at which the stream will be polled for new images.
CAPTURE_HZ = 30.0


class MjpgStreamCapture(object):
    def __init__(self, stream_url, username=None, password=None):
        """Create an mjpg-streamer capture object associated with the provided stream URL.
        
        Args:
            stream_url (str): URL to the mjpg-streamer stream (e.g., "http://localhost:8081/?action=stream")
            username (str, optional): Username for HTTP basic authentication
            password (str, optional): Password for HTTP basic authentication
        """
        self.stream_url = stream_url
        self.username = username
        self.password = password
        
        # Prepare authentication if credentials are provided
        self.auth = None
        if username and password:
            self.auth = HTTPBasicAuth(username, password)
        
        # Start a thread to continuously capture frames.
        # This must be done because different layers of buffering in the stream
        # and network will cause you to retrieve old frames if they aren't
        # continuously read.
        self._capture_frame = None
        # Use a lock to prevent access concurrent access to the stream.
        self._capture_lock = threading.Lock()
        self._capture_thread = threading.Thread(target=self._grab_frames)
        self._capture_thread.daemon = True
        self._capture_thread.start()

    def _grab_frames(self):
        """Continuously grab frames from the mjpg-streamer stream."""
        while True:
            try:
                # Make request to the stream
                response = requests.get(self.stream_url, auth=self.auth, stream=True, timeout=5)
                response.raise_for_status()
                
                # Read the MJPEG stream
                buffer = b''
                for chunk in response.iter_content(chunk_size=1024):
                    buffer += chunk
                    
                    # Look for MJPEG frame boundaries
                    while True:
                        # Find start of frame
                        start = buffer.find(b'\xff\xd8')
                        if start == -1:
                            break
                            
                        # Find end of frame
                        end = buffer.find(b'\xff\xd9', start)
                        if end == -1:
                            break
                            
                        # Extract JPEG frame (include end marker)
                        jpg = buffer[start:end+2]
                        buffer = buffer[end+2:]
                        
                        # Decode JPEG to OpenCV image
                        try:
                            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                            if frame is not None:
                                with self._capture_lock:
                                    self._capture_frame = frame
                        except Exception as e:
                            print(f"Error decoding frame: {e}")
                            
            except requests.exceptions.RequestException as e:
                print(f"Stream connection error: {e}")
                time.sleep(1)  # Wait before retrying
            except Exception as e:
                print(f"Unexpected error in stream capture: {e}")
                time.sleep(1)
                
            time.sleep(1.0 / CAPTURE_HZ)

    def read(self):
        """Read a single frame from the stream and return the data as an OpenCV
        image (which is a numpy array).
        """
        frame = None
        with self._capture_lock:
            frame = self._capture_frame
        # If there are problems, keep retrying until an image can be read.
        while frame is None:
            time.sleep(0)
            with self._capture_lock:
                frame = self._capture_frame
        # Return the capture image data.
        return frame
        
    def stop(self):
        """Stop the capture thread and cleanup resources."""
        print('{"status":"Terminating mjpg-streamer capture..."}')
        # The thread will stop when the daemon process exits
