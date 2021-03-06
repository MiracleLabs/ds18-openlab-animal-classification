from flask import Flask,render_template
from flask import request
import tensorflow as tf
import os,glob
import numpy as np
from PIL import Image
import cv2 as cv2
import sys
import os
from flask_cors import CORS
from werkzeug import secure_filename
import base64
import json


os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
port = int(os.getenv('PORT', 8000))

app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
CORS(app)
#cors = CORS(app, resources={r"/api/*": {"origins": "*"}})

#initializing the model and labels
filename = "./model.pb"
labels_filename = "./labels.txt"
graph_def = tf.GraphDef()
labels = []
@app.route('/')
def upload():
    return render_template('upload.html')
# Import the TF graph
with tf.gfile.FastGFile(filename, 'rb') as f:
     graph_def.ParseFromString(f.read())
     tf.import_graph_def(graph_def, name='')

# Create a list of labels.
with open(labels_filename, 'rt') as lf:
    for l in lf:
        labels.append(l.strip())

def convert_to_opencv(image):
    # RGB -> BGR conversion is performed as well.
    r,g,b = np.array(image).T
    opencv_image = np.array([b,g,r]).transpose()
    return opencv_image

def crop_center(img,cropx,cropy):
    h, w = img.shape[:2]
    startx = w//2-(cropx//2)
    starty = h//2-(cropy//2)
    return img[starty:starty+cropy, startx:startx+cropx]

def resize_down_to_1600_max_dim(image):
    h, w = image.shape[:2]
    if (h < 1600 and w < 1600):
        return image

    new_size = (1600 * w // h, 1600) if (h > w) else (1600, 1600 * h // w)
    return cv2.resize(image, new_size, interpolation = cv2.INTER_LINEAR)

def resize_to_256_square(image):
    h, w = image.shape[:2]
    return cv2.resize(image, (256, 256), interpolation = cv2.INTER_LINEAR)

def update_orientation(image):
    exif_orientation_tag = 0x0112
    if hasattr(image, '_getexif'):
        exif = image._getexif()
        if (exif != None and exif_orientation_tag in exif):
            orientation = exif.get(exif_orientation_tag, 1)
            # orientation is 1 based, shift to zero based and flip/transpose based on 0-based values
            orientation -= 1
            if orientation >= 4:
                image = image.transpose(Image.TRANSPOSE)
            if orientation == 2 or orientation == 3 or orientation == 6 or orientation == 7:
                image = image.transpose(Image.FLIP_TOP_BOTTOM)
            if orientation == 1 or orientation == 2 or orientation == 5 or orientation == 6:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
    return image

@app.route("/image", methods = ['GET','POST'])
def main():
    target = os.path.join(APP_ROOT, 'static/')
    print (target)
    if request.method == 'POST':
        imageFile = request.files['predimg']
        sfname = imageFile.filename
        destination = "".join([target, sfname])
        print(destination)
        imageFile.save(destination)

    print(type(imageFile))
    #initializing the model and labels
    filename = "./model.pb"
    print('model is accessing')
    labels_filename = "./labels.txt"
    
    graph_def = tf.GraphDef()
    labels = []
    # Import the TF graph
    with tf.gfile.FastGFile(filename, 'rb') as f:
        graph_def.ParseFromString(f.read())
        tf.import_graph_def(graph_def, name='')
    

    # Create a list of labels.
    with open(labels_filename, 'rt') as lf:
        for l in lf:
            labels.append(l.strip())

    # Load from a file

    print(imageFile)
    image = Image.open(imageFile).convert('RGB')
  
    # Update orientation based on EXIF tags, if the file has orientation info.
    image = update_orientation(image)

    # Convert to OpenCV format
    image = convert_to_opencv(image)
    print(image)
    # If the image has either w or h greater than 1600 we resize it down respecting
    # aspect ratio such that the largest dimension is 1600
    image = resize_down_to_1600_max_dim(image)

    # We next get the largest center square
    h, w = image.shape[:2]
    min_dim = min(w,h)
    max_square_image = crop_center(image, min_dim, min_dim)


    # Resize that square down to 256x256
    augmented_image = resize_to_256_square(max_square_image)

    # The compact models have a network size of 227x227, the model requires this size.
    network_input_size = 227
    

    # Crop the center for the specified network_input_Size
    augmented_image = crop_center(augmented_image, network_input_size, network_input_size)
    
    # These names are part of the model and cannot be changed.
    output_layer = 'loss:0'
    input_node = 'Placeholder:0'
    
    with tf.Session() as sess:
        prob_tensor = sess.graph.get_tensor_by_name(output_layer)
        predictions = sess.run(prob_tensor, {input_node: [augmented_image] })
    
    # Print the highest probability label
    highest_probability_index = np.argmax(predictions)
    s = str(highest_probability_index)
    print('Classified as: ' + labels[highest_probability_index])
    var1 = labels[highest_probability_index]
    # Or you can print out all of the results mapping labels to probabilities.
   # label_index = 0
   # for p in predictions:
    #    truncated_probablity = np.float64(np.round(p,8))
     #   print (labels, truncated_probablity)
    #    label_index += 1

    print(sfname)
    return render_template('result.html',var1=var1, sfname=sfname)
if __name__ == '__main__':
    app.run()
