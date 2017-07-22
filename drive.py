import argparse
import base64
import json
import math
import numpy as np
import socketio
import eventlet
import eventlet.wsgi
import time
from PIL import Image
from PIL import ImageOps
from flask import Flask, render_template
from io import BytesIO

import cv2

from keras.models import model_from_json
from keras.preprocessing.image import ImageDataGenerator, array_to_img, img_to_array

# Fix error with Keras and TensorFlow
import tensorflow as tf
#tf.python.control_flow_ops = tf


sio = socketio.Server()
app = Flask(__name__)
model = None
prev_image_array = None

@sio.on('telemetry')
def telemetry(sid, data):
    # The current steering angle of the car
    steering_angle = data["steering_angle"]
    # The current throttle of the car
    throttle = data["throttle"]
    # The current speed of the car
    speed = data["speed"]

    # The current image from the center camera of the car
    imgString = data["image"]
    #print(tf.shape(imgString))
    #print(imgString)

    image = Image.open(BytesIO(base64.b64decode(imgString)))
    image_array = np.asarray(image)
    image_array = cv2.cvtColor (image_array, cv2.COLOR_BGR2GRAY)
    image_array = np.subtract(np.divide(np.array(image_array).astype(np.float32), 255.0), 0.5)
    transformed_image_array = image_array[None, :, :]
    speed = float(speed) / 30.0 - 0.5;
    speed_array = np.array(float(speed)).reshape ((1, 1))
    # This model currently assumes that the features of the model are just the images. Feel free to change this.
    # steering_angle = float(model.predict(transformed_image_array, batch_size=1))
    cmd=np.array(model.predict(transformed_image_array, batch_size=1))
    # The driving model currently just outputs a constant throttle. Feel free to edit this.
    print("cmd",cmd)
    steering_angle, throttle=cmd[0]
    if speed<0.1:
        throttle+=0.1
        
    print(steering_angle, throttle, speed)
    #rospy.loginfo('%d' % steering_angle)
    send_control(steering_angle, throttle)


@sio.on('connect')
def connect(sid, environ):
    print("connect ", sid)
    send_control(0, 0)


def send_control(steering_angle, throttle):
    sio.emit("steer", data={
    'steering_angle': steering_angle.__str__(),
    'throttle': throttle.__str__()
    }, skip_sid=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Remote Driving')
    parser.add_argument('model', type=str,
    help='Path to model definition json. Model weights should be on the same path.')
    args = parser.parse_args()
    with open(args.model, 'r') as jfile:
        model = model_from_json(jfile.read())

    model.compile("adam", "mse")
    weights_file = args.model.replace('json', 'h5')
    model.load_weights(weights_file)

    # wrap Flask application with engineio's middleware
    app = socketio.Middleware(sio, app)

    # deploy as an eventlet WSGI server
    eventlet.wsgi.server(eventlet.listen(('', 4567)), app)
