#!/usr/bin/env python3
from __future__ import annotations
from typing import (
    Any,
    Tuple,
)

import logging
import time
import re

from ocr import OCR
from database import Database
from gamestate import GameState


DEFAULT_BBOX = (366, 701, 939, 192)
DEFAULT_MONSTER_BBOX = (239, 190, 1054, 478)


class RetroTracker:

    def __init__(
        self,
        ocrbox: Tuple[int, int, int, int] = DEFAULT_BBOX,
        omrbox: Tuple[int, int, int, int] = DEFAULT_MONSTER_BBOX,
    ) -> None:
        self.database = Database()
        self.gamestate = GameState(self.database)
        self.ocr = OCR(*ocrbox)
        self.omr = OCR(*omrbox)

    def __enter__(self) -> RetroTracker:
        self.database.connect()
        params = ()
        try:
            query = 'SELECT name FROM monsters'
            self.gamestate.add_nouns([
                row[0] for row in
                self.database.select(query, params)
            ])
        except Exception as e:
            pass
        return self

    def __exit__(self, *args, **kwargs) -> None:
        self.database.disconnect()

    def run(self) -> None:
        start_time = time.time()
        update_timer = 0;
        did_log = False
        while True:
            try:
                time.sleep(0.25)
                update_timer += 1
                for line in self.ocr.gen_retrommo_lines():
                    event = self.gamestate.handle_line(line)
                    if event is not None:
                        if not did_log:
                            print('')
                        did_log = True
                        print(str(event))

                if update_timer % 40 == 1:
                    if not did_log:
                        print('\r' + ' ' * 32 + '\r', end='')
                    did_log = False
                    end_time = time.time()
                    delta = end_time - start_time
                    hours = delta / (60 * 60)
                    exp = self.gamestate.exp_count // hours
                    gold = self.gamestate.gold_count // hours
                    print(f'{exp} exp/hr - {gold} gold/hr', end='', flush=True)
            except KeyboardInterrupt:
                print('  exiting')
                break
            except Exception as e:
                print(f'error: {e}')

        end_time = time.time()
        delta = end_time - start_time
        hours = delta / (60 * 60)
        self.print_stats(hours)

    def print_stats(
        self,
        hours: float,
    ) -> None:
        exp = self.gamestate.exp_count
        gold = self.gamestate.gold_count
        print(f'exp/hr - {exp//hours}')
        print(f'gld/hr - {gold//hours}')


def cmd_start(args: Any):
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('PIL.PngImagePlugin').disabled = True
    if args.bbox:
        bbox = eval(args.bbox)
        assert isinstance(bbox, tuple) and len(bbox) == 4
    elif args.position:
        import pymouse
        m = pymouse.PyMouse()
        print('position mouse at top-left of text box, then press enter')
        input('')
        x, y = m.position()
        print('now do bottom left')
        input('')
        x2, y2 = m.position()
        bbox = (x, y, x2 - x, y2 - y)
        print(f'you can use --bbox "{bbox}" instead of --position')
    else:
        bbox = DEFAULT_BBOX

    with RetroTracker(bbox) as tracker:
        tracker.database.populate_monsters_cache()
        player = tracker.database.load_player(args.player)
        tracker.gamestate.add_player(args.player_name.lower(), player)
        tracker.run()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    subparser = subparsers.add_parser('start')
    subparser.add_argument('player_name', type=str, default=None)
    subparser.add_argument('player', type=str, default=None)
    subparser.add_argument('--team', type=int, default=1)
    subparser.add_argument('--debug', action='store_true')
    subparser.add_argument('--position', action='store_true')
    subparser.add_argument('--bbox', type=str)
    subparser.set_defaults(func=cmd_start)

    args = parser.parse_args()
    args.func(args)
