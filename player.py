#!/usr/bin/env python3
from __future__ import annotations
from typing import (
    Generator,
    Optional,
    Tuple,
)

import enum


class PlayerClass(enum.Enum):
    warrior = 'warrior'
    wizard = 'wizard'
    cleric = 'cleric'


class Stats:

    stats_by_class = {
        PlayerClass.warrior: {
            'hp':  [0, 20, 26, 33, 40, 46, 53, 59, 66, 73, 79],
            'mp':  [0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0],
            'str': [0, 14, 17, 20, 23, 26, 28, 31, 34, 37, 40],
            'def': [0, 11, 13, 18, 16, 20, 22, 24, 27, 29, 31],
            'agi': [0,  8, 10, 11, 13, 14, 16, 18, 19, 21, 22],
            'int': [0,  6,  7,  8,  9, 10, 11, 12, 14, 15, 16],
            'wis': [0,  7,  9, 10, 12, 13, 14, 16, 17, 19, 20],
            'lck': [0,  8, 10, 12, 14, 15, 17, 19, 20, 22, 24],
        },
        PlayerClass.wizard: {
            'hp':  [0, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48],
            'mp':  [0, 19, 25, 31, 38, 44, 50, 56, 63, 69, 75],
            'str': [0,  6,  7,  9, 10, 11, 12, 13, 15, 16, 17],
            'def': [0,  8,  9, 11, 12, 14, 16, 17, 19, 20, 22],
            'agi': [0, 11, 13, 16, 18, 20, 22, 24, 27, 29, 31],
            'int': [0, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42],
            'wis': [0, 13, 15, 18, 20, 23, 26, 28, 31, 33, 36],
            'lck': [0, 10, 12, 14, 16, 18, 20, 22, 23, 25, 27],
        },
        PlayerClass.cleric: {
            'hp':  [0, 17, 23, 29, 35, 40, 46, 52, 58, 63, 69],
            'mp':  [0, 11, 15, 19, 23, 26, 30, 34, 38, 41, 45],
            'str': [0,  8,  9, 11, 12, 14, 16, 17, 19, 20, 22],
            'def': [0,  9, 11, 12, 14, 16, 18, 20, 21, 23, 25],
            'agi': [0, 10, 12, 14, 16, 18, 20, 22, 23, 25, 27],
            'int': [0, 12, 15, 17, 20, 22, 25, 27, 30, 32, 35],
            'wis': [0, 12, 14, 16, 19, 21, 23, 26, 28, 30, 33],
            'lck': [0, 11, 13, 16, 18, 20, 22, 24, 27, 29, 31],
        },
    }

    def __init__(
        self,
        hp: int,
        mp: int,
        strength: int,
        defense: int,
        agility: int,
        intelligence: int,
        wisdom: int,
        luck: int,
    ) -> None:
        self.hp           = hp
        self.mp           = mp
        self.strength     = strength
        self.defense      = defense
        self.agility      = agility
        self.intelligence = intelligence
        self.wisdom       = wisdom
        self.luck         = luck

    @classmethod
    def base_from_class(
        cls,
        playerClass: PlayerClass,
        level: int,
    ) -> Stats:
        return cls(
            cls.stats_by_class[playerClass]['hp'][level],
            cls.stats_by_class[playerClass]['mp'][level],
            cls.stats_by_class[playerClass]['str'][level],
            cls.stats_by_class[playerClass]['def'][level],
            cls.stats_by_class[playerClass]['agi'][level],
            cls.stats_by_class[playerClass]['int'][level],
            cls.stats_by_class[playerClass]['wis'][level],
            cls.stats_by_class[playerClass]['lck'][level],
        )

    def add(self, o: Stats) -> None:
        self.hp += o.hp
        self.mp += o.mp
        self.strength += o.strength
        self.defense += o.defense
        self.agility += o.agility
        self.intelligence += o.intelligence
        self.wisdom += o.wisdom
        self.luck += o.luck

    def __iter__(self) -> Generator[int, None, None]:
        yield self.hp
        yield self.mp
        yield self.strength
        yield self.defense
        yield self.agility
        yield self.intelligence
        yield self.wisdom
        yield self.luck


class HGear(Stats, enum.Enum):
    dented_helm = (0, 0, 0, 3, 0, 0, 0, 0)
    mage_hat = (0, 0, 0, 1, 0, 1, 2, 0)


class BGear(Stats, enum.Enum):
    leather_armor = (0, 0, 0, 3, 0, 0, 0, 0)
    tattered_cloak = (0, 0, 0, 1, 0, 0, 1, 0)


class MGear(Stats, enum.Enum):
    tenderizer = (0, 0, 8, 0, 0, 0, 0, 0)
    crooked_wand = (0, 0, 1, 0, 0, 5, 0, 0)


class OGear(Stats, enum.Enum):
    studded_shield = (0, 0, 0, 3, 0, 0, 1, 0)
    bone_bracelet = (0, 0, 1, 1, 1, 1, 1, 1)


GearType = Tuple[HGear, BGear, MGear, OGear]


class Player:

    def __init__(
        self,
        clas_: PlayerClass,
        level: int,
        gear: GearType,
        boosts: Stats,
        pid: Optional[int] = None,
    ) -> None:
        self.pid = pid
        self.gear = gear
        self.player_class = clas_
        self.level = level
        self.boosts = boosts
        self.stats = self.calculate_stats()

    def calculate_stats(self) -> Stats:
        stats = Stats.base_from_class(self.player_class, self.level)
        for gear in self.gear:
            stats.add(gear)
        stats.add(self.boosts)
        return stats
