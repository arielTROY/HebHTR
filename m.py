from HebHTR import *
from flask import *
import json, time
import os
from PIL import Image


# Create new HebHTR object.

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home_page():
    data_set ={'page': 'home', 'recognized': 'use the endpoint /detect '}
    json_dump = json.dumps(data_set)
    return json_dump

@app.route('/detect', methods=['GET'])
def detect():
    im = request.args.get('img')
    image = HebHTR(im)

# Infer words from image.
    text = img.imgToWord(iterations=5, decoder_type='best_path')
    txt=str(text)
    txt=txt[2:]
    print(txt)    
    data_set ={'page': 'home', 'recognized': txt}
    json_dump = json.dumps(data_set)
    return json_dump

if __name__ == '__main__':
    app.run(port=7777)
