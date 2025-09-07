"""Raspberry Pi Face Recognition Treasure Box
RTSP Camera Capture Device
Copyright 2013 Tony DiCola

RTSP device capture class using OpenCV. This class allows you to capture
images from an RTSP stream, as if it were a snapshot camera.

This is useful when running the code on a system where the camera is accessed
through RTSP (e.g., MediaMTX) instead of direct USB access.
"""
import threading
import time
import cv2
import numpy as np

# Rate at which the stream will be polled for new images.
CAPTURE_HZ = 30.0


class RTSPCapture(object):
    def __init__(self, rtsp_url, username=None, password=None):
        """Create an RTSP capture object associated with the provided stream URL.
        
        Args:
            rtsp_url (str): URL to the RTSP stream (e.g., "rtsp://localhost:8554/cam")
            username (str, optional): Username for RTSP authentication
            password (str, optional): Password for RTSP authentication
        """
        self.rtsp_url = rtsp_url
        self.username = username
        self.password = password
        
        # Build RTSP URL with authentication if credentials are provided
        if username and password:
            # Parse URL to insert credentials
            if rtsp_url.startswith('rtsp://'):
                # Insert credentials after protocol
                self.full_url = rtsp_url.replace('rtsp://', f'rtsp://{username}:{password}@', 1)
            else:
                self.full_url = rtsp_url
        else:
            self.full_url = rtsp_url
        
        # Open the RTSP stream
        self._camera = cv2.VideoCapture(self.full_url)
        
        # Set buffer size to reduce latency
        self._camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not self._camera.isOpened():
            raise Exception(f"Failed to open RTSP stream: {self.full_url}")
        
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
        """Continuously grab frames from the RTSP stream."""
        while True:
            try:
                retval, frame = self._camera.read()
                with self._capture_lock:
                    self._capture_frame = None
                    if retval and frame is not None:
                        self._capture_frame = frame
            except Exception as e:
                print(f"Error reading RTSP frame: {e}")
                # Try to reconnect
                try:
                    self._camera.release()
                    self._camera = cv2.VideoCapture(self.full_url)
                    self._camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception as reconnect_error:
                    print(f"Failed to reconnect to RTSP stream: {reconnect_error}")
                
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
        print('{"status":"Terminating RTSP capture..."}')
        if self._camera.isOpened():
            self._camera.release()
        # The thread will stop when the daemon process exits
