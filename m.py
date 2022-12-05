#!/usr/bin/env python
# -*- coding: utf-8 -*-
from HebHTR import *

# Create new HebHTR object.
img = HebHTR('ex.png')

# Infer words from image.
text = img.imgToWord(iterations=5, decoder_type='best_path')
txt=str(text)
txt=txt[2:]
print(txt)