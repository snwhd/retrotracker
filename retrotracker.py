#!/usr/bin/env python3
from __future__ import annotations
from typing import Any

import logging
import time
import re

from ocr import OCR
from database import Database
from gamestate import GameState


class RetroTracker:

    def __init__(self) -> None:
        self.database = Database()
        self.gamestate = GameState(self.database)
        self.ocr = OCR(180, 690, 620, 130)

    def __enter__(self) -> RetroTracker:
        self.database.connect()
        return self

    def __exit__(self, *args, **kwargs) -> None:
        self.database.disconnect()

    def run(self) -> None:
        start_time = time.time()
        while True:
            try:
                time.sleep(0.25)
                for line in self.ocr.gen_retrommo_lines():
                    event = self.gamestate.handle_line(line)
                    if event is not None:
                        print(str(event))
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


def cmd_start(tracker: RetroTracker, args: Any):
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('PIL.PngImagePlugin').disabled = True
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
    subparser.set_defaults(func=cmd_start)

    args = parser.parse_args()
    with RetroTracker() as tracker:
        args.func(tracker, args)
