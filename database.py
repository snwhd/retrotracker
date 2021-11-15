#!/usr/bin/env python3
from __future__ import annotations
import sqlite3.dbapi2 as sqlite
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


DEFAULT_DATABASE = 'stats.db'


class Database:

    def __init__(
        self,
        filename: str = DEFAULT_DATABASE,
    ) -> None:
        self.filename = filename
        self.monsters_cache: Dict[str, int] = {}
        self._connection: Optional[sqlite.Connection] = None

    @property
    def connection(self) -> sqlite.Connection:
        if self._connection is not None:
            return self._connection
        raise RuntimeError()

    def connect(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = sqlite.connect(self.filename)

    def disconnect(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self.monsters_cache = {}

    #
    # basic database io
    #

    def execute(
        self,
        query: str,
        params: Tuple,
        fetch = False,
    ) -> Optional[List[Tuple[Any, ...]]]:
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        if fetch:
            return cursor.fetchall()
        return None

    def select(
        self,
        query: str,
        params: Tuple,
    ) -> List[Tuple[Any, ...]]:
        res = self.execute(query, params, True)
        assert res is not None
        return res

    def insert(
        self,
        query: str,
        params: Tuple,
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor.lastrowid

    #
    # table initialization
    #

    def create_tables(self) -> None:
        self.execute('''CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            name STRING UNIQUE NOT NULL,
            level INTEGER,
            class STRING,
            hgear STRING,
            bgear STRING,
            mgear STRING,
            ogear STRING,
            boosts STRING,
            hp INTEGER NOT NULL,
            mp INTEGER NOT NULL,
            strength     INTEGER NOT NULL,
            defense      INTEGER NOT NULL,
            agility      INTEGER NOT NULL,
            intelligence INTEGER NOT NULL,
            wisdom       INTEGER NOT NULL,
            luck         INTEGER NOT NULL
        )''', ())
        self.execute('''CREATE TABLE IF NOT EXISTS monsters (
            id INTEGER PRIMARY KEY,
            name STRING UNIQUE NOT NULL
        )''', ())
        self.execute('''CREATE TABLE IF NOT EXISTS player_hit_monster (
            player INTEGER,
            monster INTEGER,
            ability STRING,
            damage INTGER,
            enemies INTEGER,
            FOREIGN KEY(player) REFERENCES players(id),
            FOREIGN KEY(monster) REFERENCES monsters(id)
        )''', ())
        self.execute('''CREATE TABLE IF NOT EXISTS monster_hit_player (
            player INTEGER,
            monster INTEGER,
            ability STRING,
            damage INTGER,
            friendlies INTEGER,
            FOREIGN KEY(player) REFERENCES players(id),
            FOREIGN KEY(monster) REFERENCES monsters(id)
        )''', ())

    #
    # players
    #

    def load_player(self, player_name: str) -> Player:
        rows = self.select('SELECT * FROM players WHERE name=?', (player_name,))
        if len(rows) != 1:
            raise ValueError(f'invalid player: {player_name}')
        row = cast(Tuple[int, str, int, str, str, str, str, str, str], rows[0])
        level: int = row[2]
        clas_ = PlayerClass(row[3])
        gear = (
            HGear[row[4]],
            BGear[row[5]],
            MGear[row[6]],
            OGear[row[7]],
        )
        boosts = Stats(*list(map(int, cast(str, row[8]).split())))
        return Player(
            clas_,
            level,
            gear,
            boosts,
            pid=row[0],
        )

    def player_exists(self, player_name: str) -> bool:
        rows = self.select('SELECT * FROM players WHERE name=?', (player_name,))
        return len(rows) > 0

    def insert_player(self, name: str, player: Player):
        hgear = player.gear[0].name
        bgear = player.gear[1].name
        mgear = player.gear[2].name
        ogear = player.gear[3].name
        boosts = ' '.join(map(str, tuple(player.boosts)))
        self.insert('''
            INSERT INTO players
            VALUES(NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name,
            player.level,
            player.player_class.value,
            hgear, bgear, mgear, ogear,
            boosts,
            *tuple(player.stats)
        ))

    #
    # monsters
    #

    def populate_monsters_cache(self):
        rows = self.select('SELECT * FROM monsters', ())
        for row in rows:
            row = cast(Tuple[int, str], row)
            self.monsters_cache[row[1]] = row[0]

    def get_monster_id(
        self,
        monster_name: str,
    ) -> int:
        mid = self.monsters_cache.get(monster_name)
        if mid is not None:
            return mid
        mid = self.insert(
            'INSERT INTO monsters VALUES (NULL, ?)',
            (monster_name,)
        )
        self.monsters_cache[monster_name] = mid
        return mid

    def monster_exists(self, monster_name: str) -> bool:
        rows = self.select('SELECT * FROM monsters WHERE name=?', (monster_name,))
        return len(rows) > 0

    #
    # stats
    #

    def insert_player_hit(
        self,
        player: Player,
        ability: str,
        target: int,
        damage: int,
        enemies: int,
    ) -> None:
        self.insert(
            'INSERT INTO player_hit_monster VALUES (?, ?, ?, ?, ?)',
            (player.pid, target, ability, damage, enemies),
        )

    def insert_monster_hit(
        self,
        monster: int,
        ability: str,
        player: Player,
        damage: int,
        friendlies: int,
    ) -> None:
        self.insert(
            'INSERT INTO monster_hit_player VALUES (?, ?, ?, ?, ?)',
            (player.pid, monster, ability, damage, friendlies),
        )
