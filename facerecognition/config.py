#!/usr/bin/python
# coding: utf8
"""MMM-Facial-Recognition - MagicMirror Module
Face Recognition script config
The MIT License (MIT)

Copyright (c) 2016 Paul-Vincent Roll (MIT License)
Based on work by Tony DiCola (Copyright 2013) (MIT License)
"""
import inspect
import os
import json
import sys
import platform


def to_node(type, message):
    print((json.dumps({type: message})))
    sys.stdout.flush()


_platform = platform.uname()[4]
path_to_file = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

# Size (in pixels) to resize images for training and prediction.
# Don't change this unless you also change the size of the training images.
FACE_WIDTH = 92
FACE_HEIGHT = 112

# Face detection cascade classifier configuration.
# You don't need to modify this unless you know what you're doing.
# See: http://docs.opencv.org/modules/objdetect/doc/cascade_classification.html
HAAR_FACES = path_to_file + '/haarcascade_frontalface.xml'
HAAR_SCALE_FACTOR = 1.1
HAAR_MIN_NEIGHBORS = 3
HAAR_MIN_SIZE = (20, 20)

CONFIG = json.loads(sys.argv[1]);

def get(key):
    return CONFIG[key]

def get_camera():
    to_node("status", "-" * 20)
    
    # Check if RTSP is enabled
    if get("useRTSP") == True:
        try:
            import rtsp_stream
            to_node("status", "RTSP ausgewählt...")
            rtsp_url = get("rtspUrl")
            username = get("rtspUser") if get("rtspUser") else None
            password = get("rtspPassword") if get("rtspPassword") else None
            return rtsp_stream.RTSPCapture(rtsp_url, username, password)
        except Exception as e:
            to_node("status", f"RTSP error: {str(e)}")
            to_node("status", "Falling back to mjpg-streamer...")
    
    # Check if mjpg-streamer is enabled
    if get("useMjpgStreamer") == True:
        try:
            import mjpg_stream
            to_node("status", "Mjpg-Streamer ausgewählt...")
            stream_url = get("mjpgStreamerUrl")
            username = get("mjpgStreamerUser") if get("mjpgStreamerUser") else None
            password = get("mjpgStreamerPassword") if get("mjpgStreamerPassword") else None
            return mjpg_stream.MjpgStreamCapture(stream_url, username, password)
        except Exception as e:
            to_node("status", f"Mjpg-Streamer error: {str(e)}")
            to_node("status", "Falling back to webcam...")
    
    # Try PiCam first if not using USB cam
    try:
        if get("useUSBCam") == False:
            import picam
            to_node("status", "PiCam ausgewählt...")
            cam = picam.OpenCVCapture()
            cam.start()
            return cam
        else:
            raise Exception
    except Exception:
        import webcam
        to_node("status", "Webcam ausgewählt...")
        return webcam.OpenCVCapture(device_id=0)
    to_node("status", "-" * 20)
