#!/usr/bin/env python3
from __future__ import annotations
from typing import (
    Dict,
    Optional,
)
import logging
import re

from ocr import OCR
from player import Player
from database import Database
from event import (
    EventType,
    GameEvent,
)


# First group matches the monster name (anything but dash).
# Second group matches the -1 -2 -3 etc when there are multiple
# of the same monster. We ignore this group. This also matches
# on player names.
RE_NAME = '([^-]+)(?:-+.+)?'

# Using .* instead of \d* in some places because OCR is not perfect
RE_USES_ATTACK =  re.compile(f'{RE_NAME} uses (.*) on {RE_NAME}.')
RE_TAKES_DAMAGE = re.compile(f'{RE_NAME} takes (.*) damage.')
RE_FIND_GOLD =    re.compile(r'you find (\d+) gold.')
RE_GAIN_EXP =     re.compile(r'you gain (\d+) experience.')


class GameState:

    def __init__(
        self,
        database: Database,
    ) -> None:
        self.database = database
        self.gold_count = 0
        self.exp_count = 0
        self.state = 'none'

        self.players: Dict[str, Player] = {}
        self.ability: Optional[str]  = None
        self.target: Optional[str] = None
        self.source: Optional[str] = None

    def add_player(
        self,
        username: str,
        player: Player,
    ) -> None:
        self.players[username] = player

    def handle_line(
        self,
        line: str,
    ) -> Optional[GameEvent]:
        matches = RE_USES_ATTACK.match(line)
        if matches:
            if self.state != 'none':
                # TODO: handle miss
                logging.debug(f'unexpected state for attack: {self.state}')

            source, ability, target = matches.groups()
            if source in self.players:
                self.state = 'player attacking'
                self.ability = ability
                self.target = target
                self.source = source
            elif target in self.players:
                self.state = 'monster attacking'
                self.ability = ability
                self.target = target
                self.source = source
            else:
                logging.debug(f'unknown source/target in {line}')
            return None

        matches = RE_TAKES_DAMAGE.match(line)
        if matches:
            target, damage_s = matches.groups()
            damage = OCR.int(damage_s)
            event: Optional[GameEvent] = None
            if self.state == 'player attacking':
                self.player_hits(target, damage)
                event = GameEvent(
                    EventType.player_hit,
                    source = self.source,
                    target = target,
                    damage = damage,
                    ability = self.ability,
                )
            elif self.state == 'monster attacking':
                self.monster_hits(target, damage)
                event = GameEvent(
                    EventType.monster_hit,
                    source = self.source,
                    target = target,
                    damage = damage,
                    ability = self.ability,
                )
            else:
                logging.debug(f'invalid state "{self.state}" for damage')

            self.ability = None
            self.target = None
            self.source = None
            self.state = 'none'
            return event

        matches = RE_FIND_GOLD.match(line)
        if matches:
            amount = OCR.int(matches.groups()[0])
            self.gold_count += amount
            return GameEvent(
                EventType.get_gold,
                amount = amount,
                total = self.gold_count,
            )

        matches = RE_GAIN_EXP.match(line)
        if matches:
            amount = OCR.int(matches.groups()[0])
            self.exp_count += amount
            return GameEvent(
                EventType.get_exp,
                amount = amount,
                total = self.exp_count,
            )

        logging.debug(f'unhandled: {line}')
        return None

    def player_hits(
        self,
        target: str,
        damage: int,
    ) -> None:
        if self.ability is None or self.target is None or self.source is None:
            logging.debug(f'missing parameters for player_hits')
            return
        if self.target != target:
            logging.debug(f'target mismatch: {self.target} != {target}')
            # TODO: pick best target
            return

        player = self.players.get(self.source)
        if player is None:
            logging.debug(f'invalid player hit: {self.source}')
            return

        # TODO: validate ability & monsters

        if damage > 110:
            old_damage = damage
            damage -= (damage // 100) * 100
            logging.debug(f'damage {old_damage} looks too high -> {damage}')

        mid = self.database.get_monster_id(self.target)
        self.database.insert_player_hit(
            player,
            self.ability,
            mid,
            damage,
            0,
        )

    def monster_hits(
        self,
        target: str,
        damage: int,
    ) -> None:
        if self.ability is None or self.target is None or self.source is None:
            logging.debug(f'missing parameters for monster_hits')
            return
        if self.target != target:
            logging.debug(f'target mismatch: {self.target} != {target}')
            # TODO: pick best target
            return

        player = self.players.get(target)
        if player is None:
            logging.debug(f'invalid player dmg: {target}')
            return

        # TODO: validate ability & monsters

        mid = self.database.get_monster_id(self.source)
        self.database.insert_monster_hit(
            mid,
            self.ability,
            player,
            damage,
            0,
        )
