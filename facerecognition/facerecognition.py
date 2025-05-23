#!/usr/bin/python
# coding: utf8
"""MMM-Facial-Recognition - MagicMirror Module
Face Recognition Script
The MIT License (MIT)

Copyright (c) 2016 Paul-Vincent Roll (MIT License)
Based on work by Tony DiCola (Copyright 2013) (MIT License)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import sys
import json
import time
import face
import cv2
import config
import signal

def to_node(type, message):
    # convert to json and print (node helper will read from stdout)
    try:
        print((json.dumps({type: message})))
    except Exception:
        pass
    # stdout has to be flushed manually to prevent delays in the node helper communication
    sys.stdout.flush()


to_node("status", "Facerecognition started...")

# Setup variables
current_user = None
last_match = None
detection_active = True
login_timestamp = time.time()
same_user_detected_in_row = 0

# Load training data into model
to_node("status", 'Loading training data...')

# set algorithm to be used based on setting in config.js
if config.get("recognitionAlgorithm") == 1:
    to_node("status", "ALGORITHM: LBPH")
    model = cv2.face.LBPHFaceRecognizer_create()
    model.setThreshold(config.get("lbphThreshold"))
elif config.get("recognitionAlgorithm") == 2:
    to_node("status", "ALGORITHM: Fisher")
    model = cv2.face.createFisherFaceRecognizer(threshold=config.get("fisherThreshold"))
else:
    to_node("status", "ALGORITHM: Eigen")
    model = cv2.face.createEigenFaceRecognizer(threshold=config.get("eigenThreshold"))

import os

# Get the training file path
root_dir = os.getcwd()
train_rel = config.get("trainingFile")

# If the path is absolute, use it directly, otherwise join with MagicMirror root
if os.path.isabs(train_rel):
    train_file = train_rel
else:
    train_file = os.path.join(root_dir, train_rel)

if not os.path.exists(train_file):
    raise FileNotFoundError(f"Training file not found: {train_file}")

to_node("status", f'Loading training data from: {train_file}')

# Load training file
model.read(train_file)

to_node("status", 'Training data loaded!')

# get camera
camera = config.get_camera()

def shutdown(self, signum):
    to_node("status", 'Shutdown: Cleaning up camera...')
    camera.stop()
    quit()

signal.signal(signal.SIGINT, shutdown)

# sleep for a second to let the camera warm up
time.sleep(1)

# Main Loop
while True:
    # Sleep for x seconds specified in module config
    time.sleep(config.get("interval"))
    # if detecion is true, will be used to disable detection if you use a PIR sensor and no motion is detected
    if detection_active is True:
        # Get image
        image = camera.read()
        # Convert image to grayscale.
        image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        # Get coordinates of single face in captured image.
        result = face.detect_single(image)
        # Debug logging
        if result is None:
            to_node("status", "No face detected in image")
            to_node("status", "Image size: " + str(image.shape))
        else:
            to_node("status", f"Face detected at coordinates: {result}")
            to_node("status", f"Face size: width={result[2]}, height={result[3]}")
            to_node("status", f"Image size: {image.shape}")
        # No face found, logout user?
        if result is None:
            # if last detection exceeds timeout and there is someone logged in -> logout!
            if (current_user is not None and time.time() - login_timestamp > config.get("logoutDelay")):
                # callback logout to node helper
                to_node("status", f"Logging out user {current_user} due to timeout")
                to_node("logout", {"user": current_user})
                same_user_detected_in_row = 0
                current_user = None
            continue
        # Set x,y coordinates, height and width from face detection result
        x, y, w, h = result
        # Crop image on face. If algorithm is not LBPH also resize because in all other algorithms image resolution has to be the same as training image resolution.
        if config.get("recognitionAlgorithm") == 1:
            crop = face.crop(image, x, y, w, h)
            to_node("status", f"Cropped image size: {crop.shape}")
        else:
            crop = face.resize(face.crop(image, x, y, w, h))
            to_node("status", f"Resized cropped image size: {crop.shape}")
        # Test face against model.
        label, confidence = model.predict(crop)
        # Debug logging
        to_node("status", f"Recognition result - Label: {label}, Confidence: {confidence}")
        to_node("status", f"Current threshold: {config.get('lbphThreshold') if config.get('recognitionAlgorithm') == 1 else config.get('fisherThreshold') if config.get('recognitionAlgorithm') == 2 else config.get('eigenThreshold')}")
        to_node("status", f"Image quality - Mean brightness: {crop.mean():.2f}, Std dev: {crop.std():.2f}")
        to_node("status", f"Face detection - Scale factor: {config.HAAR_SCALE_FACTOR}, Min neighbors: {config.HAAR_MIN_NEIGHBORS}")
        to_node("status", f"Same user detected in row: {same_user_detected_in_row}")
        to_node("status", f"Last match: {last_match}, Current user: {current_user}")
        # We have a match if the label is not "-1" which equals unknown because of exceeded threshold and is not "0" which are negtive training images (see training folder).
        if (label != -1 and label != 0):
            # Set login time
            login_timestamp = time.time()
            # If this is a new user or different from current user, log them in
            if (label != current_user):
                current_user = label
                # Callback current user to node helper
                to_node("login", {"user": label, "confidence": str(confidence)})
            # set last_match to current prediction
            last_match = label
        # if label is -1 or 0, current_user is not already set to unknown and last prediction match was at least 5 seconds ago
        # (to prevent unknown detection of a known user if he moves for example and can't be detected correctly)
        elif (current_user != 0 and time.time() - login_timestamp > 5):
            # Set login time
            login_timestamp = time.time()
            # set current_user to unknown
            current_user = 0
            # callback to node helper
            to_node("login", {"user": current_user, "confidence": None})
        else:
            continue
