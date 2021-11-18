#!/usr/bin/env python3
from __future__ import annotations
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Iterable,
    Set,
    Tuple,
)
import jellyfish
import logging
import enum
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
RE_SELECT_ACTION = re.compile(r'select an action.')
RE_USES_ATTACK   = re.compile(f'{RE_NAME} uses (.+) on {RE_NAME}\\.')
RE_USES_MULTI    = re.compile(f'{RE_NAME} uses (.+)\\.')
RE_TAKES_DAMAGE  = re.compile(f'{RE_NAME} takes (.+) damage.')

RE_RECOVERS_MP = re.compile(f'{RE_NAME} recovers (.+) mp\\.')
RE_RECOVERS_HP = re.compile(f'{RE_NAME} recovers (.+) hp\\.')

RE_ENEMY_APPROACHES = re.compile(r'(an enemy|enemies) approach(es)?.')
RE_NAME_DEFEATED  = re.compile(f'{RE_NAME} is defeated\\.')
RE_ENEMY_DEFEATED = re.compile(r'the enemy is defeated!')
RE_FIND_GOLD      = re.compile(r'.ou find (.+) gold.')
RE_GAIN_EXP       = re.compile(r'.ou gain (.+) experience.')


class GameStates(enum.Enum):
    not_in_battle = 'not in battle'
    selecting_action = 'selecting action'

    player_attacking = 'player attacking'
    player_attacking_multi = 'player attacking multi'
    player_using_item = 'player using item'

    monster_attacking = 'monster attacking'
    monster_attacking_multi = 'monster attacking multi'

    multi_attack = 'multi attack'


HandlerResult = Tuple[bool, Optional[GameEvent]]
HandlerMethod = Callable[[str, bool], HandlerResult]


class GameState:

    def __init__(
        self,
        database: Database,
    ) -> None:
        # database
        self.database = database
        self.second_database : Optional[Database] = None

        # player info
        self.players: Dict[str, Player] = {}

        # ocr correction
        self.known_nouns: Set[str] = set()
        self.similarity_cache: Dict[str, str] = {}

        # current state
        self.state = GameStates.not_in_battle
        self.gold_count = 0
        self.exp_count = 0

        self.ability: Optional[str]  = None
        self.target: Optional[str] = None
        self.source: Optional[str] = None

        self.state_handlers: List[HandlerMethod] = [
            # Order here matters in case one regex could
            # match on multiple strings.
            self.handle_enemy_approaches,
            self.handle_select_action,

            self.handle_uses_attack,
            self.handle_uses_multi,
            self.handle_takes_damage,

            self.handle_recovers_mp,
            self.handle_recovers_hp,

            self.handle_name_defeated,
            self.handle_enemy_defeated,

            self.handle_find_gold,
            self.handle_gain_exp,
        ]

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

    #
    # database wrapper
    #

    def player_hits(
        self,
        source: str,
        ability: str,
        target: str,
        damage: int,
        second_db = False,
    ) -> None:
        player = self.players.get(source)
        if player is None:
            logging.debug(f'invalid player hit: {source}')
            return

        # TODO: validate ability & monsters

        database = self.database
        if second_db and self.second_database is not None:
            database = self.second_database

        mid = database.get_monster_id(target)
        database.insert_player_hit(
            player,
            ability,
            mid,
            damage,
            0,
        )

    def monster_hits(
        self,
        source: str,
        ability: str,
        target: str,
        damage: int,
        second_db = False,
    ) -> None:
        player = self.players.get(target)
        if player is None:
            logging.debug(f'invalid player dmg: {target}')
            return

        # TODO: validate ability & monsters

        database = self.database
        if second_db and self.second_database is not None:
            database = self.second_database

        mid = database.get_monster_id(source)
        database.insert_monster_hit(
            mid,
            ability,
            player,
            damage,
            0,
        )

    #
    # state handling
    #

    def set_state(
        self,
        state: GameStates,
    ) -> None:
        logging.debug(f'(State Change) {self.state.value} -> {state.value}')
        self.state = state

    def clear_state(
        self,
        state = GameStates.not_in_battle,
    ) -> None:
        self.ability = None
        self.target = None
        self.source = None
        self.set_state(state)

    def check_state(
        self,
        keyword: str,
    ) -> bool:
        return keyword in self.state.value

    def expect_state(
        self,
        keywords: List[str],
        debug: str = '',
    ) -> None:
        for keyword in keywords:
            if self.check_state(keyword):
                return
        logging.debug(f'unexpected state ({debug}): {self.state}')
        self.clear_state()

    def correct_damage(self, damage: int) -> int:
        if damage > 110:
            old_damage = damage
            damage -= (damage // 100) * 100
            logging.debug(f'damage {old_damage} looks too high -> {damage}')
        return damage

    def handle_line(
        self,
        line: str,
        second_db = False,
    ) -> Optional[GameEvent]:
        for handler in self.state_handlers:
            matched, event = handler(line, second_db)
            if matched:
                return event
        return None

    def handle_enemy_approaches(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_ENEMY_APPROACHES.match(line)
        if not matches:
            return False, None

        self.expect_state(['not in battle'], 'enemy_approaches')
        self.set_state(GameStates.selecting_action)
        return True, GameEvent(EventType.enemies_approach)

    def handle_select_action(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_SELECT_ACTION.match(line)
        if not matches:
            return False, None

        self.expect_state(['selecting action', 'attacking'])
        self.set_state(GameStates.selecting_action)
        return True, None

    def handle_uses_attack(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_USES_ATTACK.match(line)
        if not matches:
            return False, None

        self.expect_state(['selecting action', 'attacking'], 'uses_attack')
        self.source = self.get_noun(matches.groups()[0])
        self.target = self.get_noun(matches.groups()[2])
        self.ability = matches.groups()[1]
        if self.source in self.players:
            self.set_state(GameStates.player_attacking)
        elif self.target in self.players:
            self.set_state(GameStates.monster_attacking)
        else:
            logging.debug(f'unknown source/target in {line}')
            self.clear_state()
        return True, None

    def handle_uses_multi(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_USES_MULTI.match(line)
        if not matches:
            return False, None

        self.expect_state(
            ['selecting action', 'attacking', 'multi attack'],
            'uses_multi',
        )
        self.source = self.get_noun(matches.groups()[0])
        self.ability = matches.groups()[1]
        if self.source in self.players:
            self.set_state(GameStates.multi_attack)
        else:
            # TODO: monster multi attack
            self.clear_state()
        return True, None

    def handle_takes_damage(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_TAKES_DAMAGE.match(line)
        if not matches:
            return False, None

        self.expect_state(['attacking', 'multi attack'], 'takes_damage')
        self.target = self.get_noun(matches.groups()[0])
        damage = OCR.parse_int(matches.groups()[1])
        damage = self.correct_damage(damage)

        source = self.source
        target = self.target
        ability = self.ability
        if source is None or target is None or ability is None:
            logging.debug(f'(takes_damage) err ({source}, {target}, {ability})')
            self.clear_state(GameStates.selecting_action)
            return True, None

        if self.state == GameStates.multi_attack:
            # In a multi-target attack we need to determine target type
            # when damage is being dealt.
            if source in self.players:
                self.set_state(GameStates.player_attacking_multi)
            else:
                self.set_state(GameStates.monster_attacking_multi)

        event: Optional[GameEvent] = None
        if self.check_state('player attacking'):
            # player attacking (multi)
            self.player_hits(source, ability, target, damage, second_db)
            event = GameEvent(
                EventType.player_hit,
                source = source,
                target = target,
                damage = damage,
                ability = self.ability,
            )
        elif self.check_state('monster attacking'):
            self.monster_hits(source, ability, target, damage, second_db)
            event = GameEvent(
                EventType.monster_hit,
                source = source,
                target = target,
                damage = damage,
                ability = self.ability,
            )
        else:
            logging.debug(f'invalid state "{self.state}" for damage')
            self.clear_state()

        if not self.check_state('multi'):
            # don't clear source when hitting multiple targets
            # TODO: how to clear this on the last one...?
            # TODO: selecting_action is incorrect here if we are
            #       in between attacks, but it will still work
            self.clear_state(GameStates.selecting_action)
        return True, event

    # TODO: Clean this up a bit, for now using an item and attacking
    #       are caught by the same regex.
    # def handle_uses_item(
    #     self,
    #     line: str,
    #     second_db: bool,
    # ) -> HandlerResult:
    #     matches = RE_USES_ITEM.match(line)
    #     if not matches:
    #         return False, None
    #     self.expect_state(['selecting action'])
    #     self.set_state(GameStates.player_using_item)
    #     return True, None

    def handle_recovers_mp(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_RECOVERS_MP.match(line)
        if not matches:
            return False, None
        self.expect_state(['player attacking'], 'recovers_mp')

        target = self.get_noun(matches.groups()[0])
        amount = OCR.parse_int(matches.groups()[1])
        event = GameEvent(
            EventType.recover_mp,
            source=self.source,
            ability=self.ability,
            target=target,
            amount=amount,
        )
        self.clear_state(GameStates.selecting_action)
        return True, event

    def handle_recovers_hp(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_RECOVERS_HP.match(line)
        if not matches:
            return False, None
        self.expect_state(['player attacking'], 'recovers_hp')

        target = self.get_noun(matches.groups()[0])
        amount = OCR.parse_int(matches.groups()[1])
        event = GameEvent(
            EventType.recover_hp,
            source=self.source,
            ability=self.ability,
            target=target,
            amount=amount,
        )
        self.clear_state(GameStates.selecting_action)
        return True, event

    def handle_enemy_defeated(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_ENEMY_DEFEATED.match(line)
        if not matches:
            return False, None
        self.set_state(GameStates.not_in_battle)
        return True, None
        # TODO: finished battle event
        # GameEvent(
        #     EventType.battle_complete,
        # )

    def handle_name_defeated(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_NAME_DEFEATED.match(line)
        if not matches:
            return False, None
        return True, None
        # TODO: monster killed event
        # GameEvent(
        #     EventType.monster_killed,
        # )

    def handle_find_gold(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_FIND_GOLD.match(line)
        if not matches:
            return False, None
        amount = OCR.parse_int(matches.groups()[0])
        self.gold_count += amount
        return True, GameEvent(
            EventType.find_gold,
            amount = amount,
            total = self.gold_count,
        )

    def handle_gain_exp(
        self,
        line: str,
        second_db: bool,
    ) -> HandlerResult:
        matches = RE_GAIN_EXP.match(line)
        if not matches:
            return False, None
        amount = OCR.parse_int(matches.groups()[0])
        self.exp_count += amount
        return True, GameEvent(
            EventType.gain_exp,
            amount = amount,
            total = self.exp_count,
        )
