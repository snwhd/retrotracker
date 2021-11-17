#!/usr/bin/env python3
from __future__ import annotations
from PIL import Image, ImageFilter
import PIL.ImageOps
import pyscreenshot as ImageGrab
import pytesseract
import unidecode
import logging
import re

from typing import (
    Generator,
    Optional,
    Tuple,
)

import warnings
warnings.filterwarnings('ignore', category=Warning)


IGNORE_REGEX = re.compile(r'(meal\)|Sa 0\))')
# replace common ocr mistakes
INT_TRANS = str.maketrans(
    'olis&y?',
    '0115677'
)


class OCR:

    def __init__(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
    ) -> None:
        self.previous_text: Optional[str] = None
        self.previous_line: Optional[str] = None
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    @staticmethod
    def parse_int(s: str) -> int:
        if s == 'psu':
            # this is a really weird but consistent edge case:
            return 20
        return int(s.translate(INT_TRANS))

    def screen_capture(self) -> Image:
        return ImageGrab.grab(bbox=[
            self.x,
            self.y,
            self.x + self.w,
            self.y + self.h,
        ])

    def set_bbox(self, x: int, y: int, w: int, h: int) -> None:
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def capture_string(self) -> str:
        image = self.screen_capture()
        r, g, b, a = image.split()
        image = Image.merge('RGB', (r, g, b))
        image = PIL.ImageOps.invert(image)
        image = image.filter(ImageFilter.BLUR)
        # image.save('/tmp/mmo.png')
        return pytesseract.image_to_string(image)

    #
    # retroMMO specific stuff
    #

    def gen_retrommo_lines(self) -> Generator[str, None, None]:
        text = unidecode.unidecode(self.capture_string().strip())
        # avoid duplicate captures
        if text != self.previous_text:
            self.previous_text = text
            for line in self.gen_split_lines(text):
                # avoid duplicate lines
                if line != self.previous_line:
                    self.previous_line = line
                    logging.debug(line)
                    yield line

    def gen_split_lines(
        self,
        text: str,
    ) -> Generator[str, None, None]:
        for s in text.split('\n'):
            s = s.strip()
            if s != '' and len(s) > 5 and not self.ignore(s):
                yield s.lower()

    def ignore(
        self,
        text: str,
    ) -> bool:
        return IGNORE_REGEX.match(text) is not None
