from HebHTR import *
from flask import *
import json
from io import BytesIO
import requests
from PIL import Image

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home_page():
    data_set = {'page': 'home', 'recognized': 'use the endpoint /detect '}
    json_dump = json.dumps(data_set)
    return json_dump

@app.route('/detect', methods=['GET'])
def detect():
    img_url = request.args.get('img')
    
    # Fetch image from the URL
    response = requests.get(img_url)
    image = Image.open(BytesIO(response.content))
    
    # Create HebHTR object and process image
    htr = HebHTR(image)
    text = htr.imgToWord(iterations=5, decoder_type='best_path')
    
    txt = str(text)
    txt = txt[2:]
    print(txt)
    
    data_set = {'page': 'home', 'recognized': txt}
    json_dump = json.dumps(data_set)
    return json_dump

if __name__ == '__main__':
    app.run(port=7777)
