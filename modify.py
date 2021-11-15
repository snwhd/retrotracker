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

from player import (
    BGear,
    HGear,
    MGear,
    OGear,
    Player,
    PlayerClass,
    Stats,
)

from retrotracker import RetroTracker


PRESET_PLAYERS = {
    'wr.str': Player(
        PlayerClass.warrior,
        10,
        (HGear.dented_helm, BGear.leather_armor, MGear.tenderizer, OGear.studded_shield),
        Stats(0, 0, 6, 0, 0, 0, 0, 0),
    ),
    'wr.def': Player(
        PlayerClass.warrior,
        10,
        (HGear.dented_helm, BGear.leather_armor, MGear.tenderizer, OGear.studded_shield),
        Stats(0, 0, 0, 6, 0, 0, 0, 0),
    ),
    'wz.int': Player(
        PlayerClass.wizard,
        10,
        (HGear.mage_hat, BGear.tattered_cloak, MGear.crooked_wand, OGear.bone_bracelet),
        Stats(0, 0, 0, 0, 0, 6, 0, 0),
    ),
}


def cmd_create(tracker: RetroTracker, args: Any):
    tracker.database.create_tables()


def cmd_presets(tracker: RetroTracker, args: Any):
    database = tracker.database
    for name, player in PRESET_PLAYERS.items():
        if not database.player_exists(name):
            database.insert_player(name, player)


def cmd_add_player(tracker: RetroTracker, args: Any):
    database = tracker.database

    name = input('player alias/name (e.g. wr.str): ')
    if database.player_exists(name):
        print('alias already exists')
        return

    option: Any = None # for typing

    print('--- available classes ---')
    for option in PlayerClass:
        print(f'  {option.name}')
    cls = PlayerClass(input('class: '))
    level = int(input('level (1-10): '))
    assert 0 < level <= 10, 'invalid level'

    print('--- headgear options ---')
    for option in HGear:
        print(f'  {option.name}')
    hgear = HGear[input('hgear: ')]

    print('--- bodygear options ---')
    for option in BGear:
        print(f'  {option.name}')
    bgear = BGear[input('bgear: ')]

    print('--- mainhand options ---')
    for option in MGear:
        print(f'  {option.name}')
    mgear = MGear[input('mgear: ')]

    print('--- offhand gear options ---')
    for option in OGear:
        print(f'  {option.name}')
    ogear = OGear[input('ogear: ')]

    while True:
        boosts_inputs = []
        for stat in ('str', 'def', 'agi', 'int', 'wis', 'lck'):
            n = int(input(f'{stat} boosts (0-6): '))
            boosts_inputs.append(n)
        if sum(boosts_inputs) > 6:
            raise ValueError('thats too many boosts!')
            continue
        break
    boosts = Stats(0, 0, *boosts_inputs)
    player = Player(cls, level, (hgear, bgear, mgear, ogear), boosts)
    database.insert_player(name, player)


def cmd_rename_player(tracker: RetroTracker, args: Any):
    database = tracker.database
    source = args.source
    dest = args.dest
    if not database.player_exists(source):
        print(f'no such player: "{source}"')
        return

    if database.player_exists(dest):
        print(f'player "{dest}" already, exists. Did you mean "merge_players"')
        return

    confirm = input(f'confirm renaming {source} to {dest} (y/N):')
    if confirm.lower().strip().startswith('y'):
        params = (dest, source)
        database.insert('UPDATE players SET name=? WHERE name=?', params)


def cmd_merge_players(tracker: RetroTracker, args: Any):
    database = tracker.database
    source = args.source
    dest = args.dest
    if not database.player_exists(source):
        print(f'no such player: "{source}"')
        return

    if not database.player_exists(dest):
        print(f'no such player: "{source}". Did you mean "rename_player"')
        return

    print('you cannot undo this action!')
    confirm = input(f'confirm merging player {source} into {dest} (y/N):')
    if confirm.lower().strip().startswith('y'):
        rows = database.select('SELECT id FROM players WHERE name=?', (source,))
        if len(rows) != 1:
            raise RuntimeError('unexpected query result: {rows}')
        old_id = rows[0][0]

        rows = database.select('SELECT id FROM players WHERE name=?', (dest,))
        if len(rows) != 1:
            raise RuntimeError('unexpected query result: {rows}')
        new_id = rows[0][0]

        database.insert(
            'UPDATE player_hit_monster SET player=? WHERE player=?',
            (new_id, old_id),
        )
        database.insert(
            'UPDATE monster_hit_player SET player=? WHERE player=?',
            (new_id, old_id),
        )
        database.insert('DELETE FROM players WHERE id=?', (old_id,))


def cmd_delete_player(tracker: RetroTracker, args: Any):
    database = tracker.database

    name = args.name
    rows = database.select('SELECT id FROM players WHERE name=?', (name,))
    if len(rows) != 1:
        print(f'no such player: "{name}"')
        return
    pid = cast(int, rows[0][0])

    print('you cannot undo this action!')
    confirm = input(f'confirm deleting player {name} (y/N):')
    if confirm.lower().strip().startswith('y'):
        database.insert('DELETE FROM player_hit_monster WHERE player=?', (pid,))
        database.insert('DELETE FROM monster_hit_player WHERE player=?', (pid,))
        database.insert('DELETE FROM players WHERE id=?', (pid,))

####################


def cmd_rename_monster(tracker: RetroTracker, args: Any):
    database = tracker.database
    source = args.source
    dest = args.dest
    if not database.monster_exists(source):
        print(f'no such monster: "{source}"')
        return

    if database.monster_exists(dest):
        print(f'monster "{dest}" already, exists. Did you mean "merge_monsters"')
        return

    confirm = input(f'confirm renaming "{source}" to "{dest}" (y/N):')
    if confirm.lower().strip().startswith('y'):
        params = (dest, source)
        database.insert('UPDATE monsters SET name=? WHERE name=?', params)


def cmd_merge_monsters(tracker: RetroTracker, args: Any):
    database = tracker.database
    source = args.source
    dest = args.dest
    if not database.monster_exists(source):
        print(f'no such monster: "{source}"')
        return

    if not database.monster_exists(dest):
        print(f'no such monster: "{source}". Did you mean "rename_monster"')
        return

    print('you cannot undo this action!')
    confirm = input(f'confirm merging monster "{source}" into "{dest}" (y/N):')
    if confirm.lower().strip().startswith('y'):
        rows = database.select('SELECT id FROM monsters WHERE name=?', (source,))
        if len(rows) != 1:
            raise RuntimeError('unexpected query result: {rows}')
        old_id = rows[0][0]

        rows = database.select('SELECT id FROM monsters WHERE name=?', (dest,))
        if len(rows) != 1:
            raise RuntimeError('unexpected query result: {rows}')
        new_id = rows[0][0]

        database.insert(
            'UPDATE player_hit_monster SET monster=? WHERE monster=?',
            (new_id, old_id),
        )
        database.insert(
            'UPDATE monster_hit_player SET monster=? WHERE monster=?',
            (new_id, old_id),
        )
        database.insert('DELETE FROM monsters WHERE id=?', (old_id,))


def cmd_delete_monster(tracker: RetroTracker, args: Any):
    database = tracker.database

    name = args.name
    rows = database.select('SELECT id FROM monsters WHERE name=?', (name,))
    if len(rows) != 1:
        print(f'no such monster: "{name}"')
        return
    mid = cast(int, rows[0][0])

    print('you cannot undo this action!')
    confirm = input(f'confirm deleting monster {name} (y/N):')
    if confirm.lower().strip().startswith('y'):
        database.insert('DELETE FROM player_hit_monster WHERE monster=?', (mid,))
        database.insert('DELETE FROM monster_hit_player WHERE monster=?', (mid,))
        database.insert('DELETE FROM monsters WHERE id=?', (mid,))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    subparser = subparsers.add_parser('create')
    subparser.set_defaults(func=cmd_create)

    subparser = subparsers.add_parser('create_presets')
    subparser.set_defaults(func=cmd_presets)

    subparser = subparsers.add_parser('add_player')
    subparser.set_defaults(func=cmd_add_player)

    subparser = subparsers.add_parser('rename_player')
    subparser.add_argument('source', type=str, help='current name')
    subparser.add_argument('dest', type=str, help='new name')
    subparser.set_defaults(func=cmd_rename_player)

    subparser = subparsers.add_parser('merge_players')
    subparser.add_argument('source', type=str, help='merge from')
    subparser.add_argument('dest', type=str, help='merge into')
    subparser.set_defaults(func=cmd_merge_players)

    subparser = subparsers.add_parser('delete_player')
    subparser.add_argument('name', type=str)
    subparser.set_defaults(func=cmd_delete_player)

    subparser = subparsers.add_parser('rename_monster')
    subparser.add_argument('source', type=str, help='current name')
    subparser.add_argument('dest', type=str, help='new name')
    subparser.set_defaults(func=cmd_rename_monster)

    subparser = subparsers.add_parser('merge_monsters')
    subparser.add_argument('source', type=str, help='merge from')
    subparser.add_argument('dest', type=str, help='merge into')
    subparser.set_defaults(func=cmd_merge_monsters)

    subparser = subparsers.add_parser('delete_monster')
    subparser.add_argument('name', type=str)
    subparser.set_defaults(func=cmd_delete_monster)

    args = parser.parse_args()
    with RetroTracker() as tracker:
        if hasattr(args, 'func'):
            args.func(tracker, args)
        else:
            print('must provide a subcommand')
            for choice in subparsers.choices:
                print(f'  {choice}')
