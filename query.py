#!/usr/bin/env python3
from __future__ import annotations
import logging
import time
import re

from typing import (
    cast,
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)

import numpy

from retrotracker import RetroTracker


MONSTER_HP_LOOKUP = {
    'lizard': 15,
    'goblin archer': 32,
    'goblin grunt': 35,
    'goblin warrior': 39,
    'cave bat': 28,
}


def cmd_players(tracker: RetroTracker, args: Any):
    where = ''
    params: Tuple = ()
    if args.name is not None:
        where = 'WHERE name=?'
        params = (args.name,)
    rows: List[Tuple[Any, ...]] = tracker.database.select(f'''
        SELECT
            name,
            class,
            level,
            strength,
            defense,
            agility,
            intelligence,
            wisdom,
            luck
        FROM players
        {where}
    ''', params)
    for row in rows:
        row = cast(Tuple[str, str, int, int, int, int, int, int, int], row)
        name, cls, level, s, d, a, i, w, l = row
        print(f'-- {name} Lv {level} {cls} --')
        print(f'   str: {s}')
        print(f'   def: {d}')
        print(f'   agi: {a}')
        print(f'   int: {i}')
        print(f'   wiz: {w}')
        print(f'   lck: {l}')


def cmd_player_hit(tracker: RetroTracker, args: Any):
    player = args.player
    monster = args.monster
    rows = tracker.database.select('''
        SELECT
            h.ability,
            h.damage
        FROM player_hit_monster as h
            JOIN players AS p ON h.player = p.id
            JOIN monsters AS m ON h.monster = m.id
        WHERE
            m.name = ? AND
            p.name = ?
    ''', (monster, player))
    by_ability: Dict[str, List[int]] = {}
    for row in rows:
        row = cast(Tuple[str, int], row)
        ability, damage = row
        if ability not in by_ability:
            by_ability[ability] = []
        by_ability[ability].append(damage)

    for ability, hits in by_ability.items():
        avg = numpy.average(hits)
        std = numpy.std(hits)
        max_hp = MONSTER_HP_LOOKUP.get(monster)
        oneshot_chance = ''
        if max_hp is not None:
            oneshots = numpy.where(numpy.array(hits) >= max_hp)[0]
            chance = (len(oneshots) / len(hits)) * 100
            oneshot_chance = f'({chance:0.02f}% one-shot)'
        print(f'{ability} - n={len(hits)} avg={avg:0.02f} std={std:0.02f} {oneshot_chance}')


def cmd_monsters(tracker: RetroTracker, args: Any):
    for row in tracker.database.select('SELECT name FROM monsters', ()):
        print(row[0])


def cmd_monster_hit(tracker: RetroTracker, args: Any):
    player = args.player
    monster = args.monster
    rows = tracker.database.select('''
        SELECT
            h.ability,
            h.damage
        FROM monster_hit_player as h
            JOIN players as p ON h.player = p.id
            JOIN monsters as m ON h.monster = m.id
        WHERE
            m.name = ? AND
            p.name = ?
    ''', (monster, player))
    by_ability: Dict[str, List[int]] = {}
    for row in rows:
        row = cast(Tuple[str, int], row)
        ability, damage = row
        if ability not in by_ability:
            by_ability[ability] = []
        by_ability[ability].append(damage)

    for ability, hits in by_ability.items():
        avg = numpy.average(hits)
        std = numpy.std(hits)
        max_hp = MONSTER_HP_LOOKUP.get(monster)
        print(f'{ability} - n={len(hits)} avg={avg:0.02f} std={std:0.02f}')


def cmd_encounter(tracker: RetroTracker, args: Any):
    encounter: Optional[int] = args.encounter_id
    if encounter is None:
        rows = tracker.database.select('''
            SELECT
                c.id,
                c.exp,
                c.gold,
                (SELECT COUNT(*) FROM encounter_items as i WHERE i.encounter = c.id),
                (SELECT COUNT(*) FROM encounter_monsters as m WHERE m.encounter = c.id),
                (SELECT COUNT(*) FROM encounter_players p WHERE p.encounter = c.id)
            FROM encounters as c
        ''', ())
        for row in rows:
            eid, exp, gold, ni, nm, np = row
            gold = gold or 0
            exp = exp or 0
            print(f'{eid:>3} - {np}v{nm} {exp} exp, {gold} gold')
        return

    # otherwise, detailed output
    rows = tracker.database.select(
        'SELECT exp, gold FROM encounters WHERE id=?',
        (encounter,)
    )
    assert len(rows) == 1
    exp, gold = cast(Tuple[int, int], rows[0])

    rows = tracker.database.select('''
        SELECT
            m.name
        FROM encounter_monsters AS em
            JOIN monsters AS m ON em.monster = m.id
        WHERE em.encounter = ?
    ''', (encounter,))
    monsters: List[str] = [row[0] for row in rows]

    rows = tracker.database.select('''
        SELECT
            ep.username,
            p.name
        FROM encounter_players AS ep
            JOIN players AS p ON ep.player = p.id
        WHERE ep.encounter = ?
    ''', (encounter,))
    players = cast(List[Tuple[str, str]], list(rows))

    print(f'encounter {encounter} -- {len(players)}v{len(monsters)}')
    print(f'monsters: {", ".join(monsters)}')
    print(f'        player        damage dealt    damage taken')
    print(f'        ------        ------------    ------------')
    for username, classname in players:
        dealt = tracker.database.select('''
            SELECT SUM(h.damage)
            FROM player_hit_monster as h
                JOIN encounters AS e ON e.id = h.encounter
                JOIN encounter_players as p ON
                    e.id = p.encounter AND p.player = h.player
            WHERE e.id=? AND p.username=?
        ''', (encounter, username))[0][0] or 0
        taken = tracker.database.select('''
            SELECT SUM(h.damage)
            FROM monster_hit_player as h
                JOIN encounters AS e ON e.id = h.encounter
                JOIN encounter_players as p ON
                    e.id = p.encounter AND p.player = h.player
            WHERE e.id=? AND p.username=?
        ''', (encounter, username))[0][0] or 0
        name = f'{username} ({classname})'
        print(f'{name:^22s} {str(dealt):^12s}    {str(taken):^12s}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    subparser = subparsers.add_parser('players')
    subparser.add_argument('--name', type=str, default=None)
    subparser.set_defaults(func=cmd_players)

    subparser = subparsers.add_parser('player_hit')
    subparser.add_argument('player', type=str)
    subparser.add_argument('monster', type=str)
    subparser.set_defaults(func=cmd_player_hit)

    subparser = subparsers.add_parser('monsters')
    subparser.set_defaults(func=cmd_monsters)

    subparser = subparsers.add_parser('monster_hit')
    subparser.add_argument('monster', type=str)
    subparser.add_argument('player', type=str)
    subparser.set_defaults(func=cmd_monster_hit)

    subparser = subparsers.add_parser('encounter')
    subparser.add_argument('encounter_id', type=int, nargs='?', default=None)
    subparser.set_defaults(func=cmd_encounter)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        with RetroTracker() as tracker:
            args.func(tracker, args)
    else:
        print('must provide a subcommand')
        for choice in subparsers.choices:
            print(f'  {choice}')
