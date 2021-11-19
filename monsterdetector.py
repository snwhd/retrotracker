#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from PIL import Image
from typing import (
    cast,
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Set,
)

import base64
import json
import logging
import os
import zlib


REDUCED_SIZE = (32, 32)


# (BW_Img, AVG_Color)
ReducedImage = Tuple[Image.Image, Tuple[int, int, int]]


class MonsterDetector:

    def __init__(self) -> None:
        self.filename = 'monsters.json'
        self.dataset = self.load(self.filename)
        self.ignored_names: Set[str] = set()

    def load_baseline(
        self,
        filename: str,
        monster_name: str,
        ignore = False,
    ) -> None:
        if monster_name in self.dataset:
            logging.error(f'[MonsterDetector] conflicting name {monster_name}')
            return
        image = Image.open(filename)
        self.dataset[monster_name] = self.reduce(image)
        if ignore:
            self.ignored_names.add(monster_name)

    def save(self) -> None:
        data: Dict[str, Any] = {}
        for name, (image, avg) in self.dataset.items():
            image_data = base64.b64encode(zlib.compress(image.tobytes()))
            data[name] = {
                'img': image_data.decode('utf-8'),
                'avg': avg,
            }

        with open(self.filename, 'w') as f:
            f.write(json.dumps(data, indent=4))

    def dump(self, directory: str) -> None:
        path = Path(directory)
        if not path.exists():
            path.mkdir()

        for name, (image, avg) in self.dataset.items():
            ipath = path / f'{name}.png'
            with ipath.open('wb') as f:
                image.save(f)

    def identify(self, image: Image.Image) -> List[str]:
        monster_images = self.split(image)
        logging.debug(f'[MonsterDetector] identifying {len(monster_images)}')
        reduced = map(self.reduce, monster_images)
        nearest = map(self.find_nearest, reduced)
        monsters: List[str] = []
        for monster in nearest:
            if monster in self.ignored_names:
                logging.debug(f'ignoring monster: {monster}')
                continue
            monsters.append(monster)
        return monsters

    def find_nearest(self, reduced: ReducedImage) -> str:
        best_score = 0.0
        best_name = ''
        for name, baseline in self.dataset.items():
            score = self.similarity(reduced, baseline)
            if score == 1.0:
                # perfect score, quit early
                return name
            if score > best_score:
                best_score = score
                best_name = name
        return best_name

    @staticmethod
    def load(filename: str) -> Dict[str, ReducedImage]:
        dataset: Dict[str, ReducedImage] = {}
        if os.path.exists(filename):
            with open(filename) as f:
                json_data = json.loads(f.read())
            for name in json_data:
                compressed: str = json_data[name]['img']
                decompressed = zlib.decompress(base64.b64decode(compressed))
                image = Image.frombytes('1', REDUCED_SIZE, decompressed)
                avg = cast(Tuple[int, int, int], tuple(json_data[name]['avg']))
                dataset[name] = (image, avg)
        return dataset

    @staticmethod
    def build() -> MonsterDetector:
        savedata = Path('monsters.json')
        # TODO: warn about deletion?
        if savedata.exists():
            savedata.unlink()

        detector = MonsterDetector()
        detector.load_baseline('res/retrommo/caveBat.png', 'cave bat')
        detector.load_baseline('res/retrommo/bigGobble.png', 'big gobble')
        detector.load_baseline('res/retrommo/cursedCandle.png','cursed candle')
        detector.load_baseline('res/retrommo/dimitri.png','dimitri')
        detector.load_baseline('res/retrommo/doomShroom.png','doom shroom')
        detector.load_baseline('res/retrommo/evilStump.png','evil stump')
        detector.load_baseline('res/retrommo/goblinGrunt.png','goblin grunt')
        detector.load_baseline('res/retrommo/goblinArcher.png','goblin archer')
        detector.load_baseline('res/retrommo/goblinJester.png','goblin jester')
        detector.load_baseline('res/retrommo/goblinJuggler.png','goblin juggler')
        detector.load_baseline('res/retrommo/goblinMage.png','goblin mage')
        detector.load_baseline('res/retrommo/goblinStrongman.png','goblin strongman')
        detector.load_baseline('res/retrommo/goblinWarrior.png','goblin warrior')
        detector.load_baseline('res/retrommo/killerWasp.png','killer wasp')
        detector.load_baseline('res/retrommo/lizard.png','lizard')
        detector.load_baseline('res/retrommo/madTurkey.png','mad turkey')
        detector.load_baseline('res/retrommo/magicMoth.png','magic moth')
        detector.load_baseline('res/retrommo/medamaude.png','medamaude')
        detector.load_baseline('res/retrommo/phantomKnight.png','phantom knight')
        detector.load_baseline('res/retrommo/skullBat.png','skull bat')
        detector.load_baseline('res/retrommo/sludge.png','sludge')
        detector.load_baseline('res/retrommo/spider.png','spider')
        detector.load_baseline('res/retrommo/watcher.png','watcher')
        detector.load_baseline('res/retrommo/cursor.png','cursor', ignore=True)
        return detector

    @staticmethod
    def split(image: Image) -> List[Image]:
        background_color = (0, 0, 0)
        images: List[Image] = []
        monsters: List[Tuple[int, int, int, int]] = []

        image = image.convert('RGB')
        width, height = image.size

        monster_start: Optional[int] = None
        y_lo: Optional[int] = None
        y_hi: Optional[int] = None
        for x in range(image.width):
            pixel_found = False
            for y in range(image.height):
                pixel = image.getpixel((x, y))
                if pixel != (0, 0, 0):
                    pixel_found = True
                    if monster_start is None:
                        monster_start = x
                    if y_lo is None or y < y_lo:
                        y_lo = y
                    if y_hi is None or y > y_hi:
                        y_hi = y
            if (
                not pixel_found
                and monster_start is not None
                and y_lo is not None
                and y_hi is not None
            ): # end of monster
                monsters.append((monster_start, y_lo, x - 1, y_hi))
                monster_start = None
                y_lo = None
                y_hi = None
        return [image.crop(m) for m in monsters]

    @staticmethod
    def reduce(image: Image) -> ReducedImage:
        image = image.convert('RGBA')

        colors: List[Tuple[int, int, int, int]] = []
        new_image = Image.new('1', REDUCED_SIZE)
        pixels = new_image.load()

        image = image.resize(REDUCED_SIZE, resample=Image.NEAREST)
        for x in range(new_image.width):
            for y in range(new_image.height):
                pixel = image.getpixel((x, y))
                if pixel[:3] != (0, 0, 0) and pixel[3] != 0:
                    colors.append(pixel)
                    pixels[x,y] = 1
        color_sum = [0, 0, 0]
        for r, g, b, a in colors:
            color_sum[0] += r
            color_sum[1] += g
            color_sum[2] += b
        avg = (
            color_sum[0] // len(colors),
            color_sum[1] // len(colors),
            color_sum[2] // len(colors),
        )
        return (new_image, avg)

    @staticmethod
    def similarity(a: ReducedImage, b: ReducedImage) -> float:
        a_img, a_avg = a
        b_img, b_avg = b
        if a_img.size != b_img.size:
            logging.error('[BattleParser] similarity size mismatch')
            return 0.0

        matches = 0
        for x in range(a_img.width):
            for y in range(a_img.height):
                if a_img.getpixel((x,y)) == b_img.getpixel((x,y)):
                    matches += 1

        return matches / (a_img.width * a_img.height)


def cmd_build(args: Any) -> None:
    detector = MonsterDetector.build()
    detector.save()


def cmd_dump(args: Any) -> None:
    detector = MonsterDetector()
    detector.dump('res/outputs')


def cmd_identify(args: Any) -> None:
    path = Path(args.filename)
    if path.exists():
        detector = MonsterDetector()
        image = Image.open(str(path))
        print(detector.identify(image))
    else:
        print(f'no such file: {path}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    subparser = subparsers.add_parser('build')
    subparser.set_defaults(func=cmd_build)

    subparser = subparsers.add_parser('dump')
    subparser.set_defaults(func=cmd_dump)

    subparser = subparsers.add_parser('identify')
    subparser.add_argument(
        'filename',
        type=str,
        help='screenshot of monsters w/ black bg',
    )
    subparser.set_defaults(func=cmd_identify)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print('must provide a subcommand')
        for choice in subparsers.choices:
            print(f'  {choice}')
