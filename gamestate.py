#!/usr/bin/env python3
from __future__ import annotations
from typing import (
    Dict,
    List,
    Optional,
    Iterable,
    Set,
    Tuple,
)
import jellyfish
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
RE_USES_ATTACK =  re.compile(f'{RE_NAME} uses (.+) on {RE_NAME}.')
RE_USES_MULTI =   re.compile(f'{RE_NAME} uses (.+).')
RE_TAKES_DAMAGE = re.compile(f'{RE_NAME} takes (.+) damage.')
RE_FIND_GOLD =    re.compile(r'.ou find (.+) gold.')
RE_GAIN_EXP =     re.compile(r'.ou gain (.+) experience.')


class GameState:

    def __init__(
        self,
        database: Database,
    ) -> None:
        self.database = database
        self.second_database : Optional[Database] = None
        self.gold_count = 0
        self.exp_count = 0
        self.state = 'none'

        self.known_nouns: Set[str] = set()
        self.similarity_cache: Dict[str, str] = {}

        self.players: Dict[str, Player] = {}
        self.ability: Optional[str]  = None
        self.target: Optional[str] = None
        self.source: Optional[str] = None

    def init_second_db(self) -> None:
        self.second_database = Database()
        self.second_database.connect()
        self.second_database.populate_monsters_cache()

    def close_second_db(self) -> None:
        if self.second_database is not None:
            self.second_database.disconnect()
            self.second_database = None

    def add_player(
        self,
        username: str,
        player: Player,
    ) -> None:
        self.players[username] = player
        self.add_nouns([username])

    def remove_players(self) -> None:
        for username in self.players:
            self.known_nouns.remove(username)
        self.players = {}

    def add_nouns(self, nouns: Iterable[str]) -> None:
        for n in nouns:
            self.known_nouns.add(n)
        self.similarity_cache = {}

    def get_noun(self, s: str) -> str:
        if s in self.similarity_cache:
            return self.similarity_cache[s]
        lowest_noun = s
        lowest_dist = 4
        # TODO: what if its a new monster type
        for noun in self.known_nouns:
            dist = jellyfish.levenshtein_distance(s, noun)
            if dist < lowest_dist:
                lowest_dist = dist
                lowest_noun = noun
        self.similarity_cache[s] = lowest_noun
        if s != lowest_noun:
            logging.debug(f'corrected "{s}" to "{lowest_noun}"')
        return lowest_noun

    def clear_state(self) -> None:
        self.state = 'none'
        self.ability = None
        self.target = None
        self.source = None

    def handle_line(
        self,
        line: str,
        second_db = False,
    ) -> Optional[GameEvent]:
        matches = RE_USES_ATTACK.match(line)
        if matches:
            if self.state != 'none':
                # TODO: handle miss
                logging.debug(f'unexpected state for attack: {self.state}')
                self.clear_state()

            source, ability, target = matches.groups()
            self.ability = ability
            self.target = self.get_noun(target)
            self.source = self.get_noun(source)
            if source in self.players:
                self.state = 'player attacking'
            elif target in self.players:
                self.state = 'monster attacking'
            else:
                logging.debug(f'unknown source/target in {line}')
                self.clear_state()
            return None

        matches = RE_USES_MULTI.match(line)
        if matches:
            if self.state != 'none':
                # TODO: handle miss
                logging.debug(f'unexpected state for attack: {self.state}')
                self.clear_state()

            source, ability = matches.groups()
            source = self.get_noun(source)
            if source in self.players:
                self.state = 'multi-attack'
                self.ability = ability
                self.source = source
            return None

        matches = RE_TAKES_DAMAGE.match(line)
        if matches:
            target, damage_s = matches.groups()
            damage = OCR.parse_int(damage_s)
            target = self.get_noun(target)

            if damage > 110:
                old_damage = damage
                damage -= (damage // 100) * 100
                logging.debug(f'damage {old_damage} looks too high -> {damage}')

            if self.state == 'multi-attack':
                if target in self.players:
                    self.state = 'player attacking multi'
                else:
                    self.state = 'monster attacking multi'

            event: Optional[GameEvent] = None
            if self.state in ('player attacking', 'player attacking multi'):
                self.player_hits(target, damage, second_db)
                event = GameEvent(
                    EventType.player_hit,
                    source = self.source,
                    target = target,
                    damage = damage,
                    ability = self.ability,
                )
            elif self.state in ('monster attacking', 'monster attacking multi'):
                self.monster_hits(target, damage, second_db)
                event = GameEvent(
                    EventType.monster_hit,
                    source = self.source,
                    target = target,
                    damage = damage,
                    ability = self.ability,
                )
            else:
                logging.debug(f'invalid state "{self.state}" for damage')
                self.clear_state()

            if 'multi' not in self.state:
                # don't clear source when hitting multiple targets
                # TODO: how to clear this on the last one...?
                self.clear_state()
            return event

        matches = RE_FIND_GOLD.match(line)
        if matches:
            amount = OCR.parse_int(matches.groups()[0])
            self.gold_count += amount
            return GameEvent(
                EventType.get_gold,
                amount = amount,
                total = self.gold_count,
            )

        matches = RE_GAIN_EXP.match(line)
        if matches:
            amount = OCR.parse_int(matches.groups()[0])
            self.exp_count += amount
            return GameEvent(
                EventType.get_exp,
                amount = amount,
                total = self.exp_count,
            )

        return None

    def player_hits(
        self,
        target: str,
        damage: int,
        second_db = False,
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

        database = self.database
        if second_db and self.second_database is not None:
            database = self.second_database

        mid = database.get_monster_id(self.target)
        database.insert_player_hit(
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
        second_db = False,
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

        database = self.database
        if second_db and self.second_database is not None:
            database = self.second_database

        mid = database.get_monster_id(self.source)
        database.insert_monster_hit(
            mid,
            self.ability,
            player,
            damage,
            0,
        )
