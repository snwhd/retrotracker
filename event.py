#!/usr/bin/env python3
from __future__ import annotations
from typing import Optional
import enum


class EventType(enum.Enum):
    monster_hit = 'monster_hit'
    player_hit = 'player_hit'
    find_gold = 'find_gold'
    find_item = 'find_item'
    gain_exp = 'gain_exp'
    recover_mp = 'recover mp'
    recover_hp = 'recover hp'
    enemies_approach = 'enemies approach'


class GameEvent:

    def __init__(
        self,
        typ: EventType,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
        ability: Optional[str] = None,
        amount: Optional[int] = None,
        total: Optional[int] = None,
        damage: Optional[int] = None,
        item: Optional[str] = None,
        encounter: Optional[int] = None,
    ) -> None:
        self.type = typ
        self._target = target
        self._total = total
        self._source = source or item
        self._amount = amount or damage or encounter
        self._ability = ability
        self.extra_text = ''

    def __str__(self) -> str:
        if self.type in (EventType.monster_hit, EventType.player_hit):
            return f'{self.source} used {self.ability} on {self.target} ({self.damage} damage)'
        if self.type == EventType.find_gold:
            return f'you found {self.amount} gold'
        if self.type == EventType.gain_exp:
            return f'you gained {self.amount} experience'
        if self.type == EventType.find_item:
            return f'you found an item: {self.item}'
        if self.type == EventType.recover_mp:
            return f'{self.source} used {self.ability} on {self.target} ({self.amount} mp)'
        if self.type == EventType.recover_hp:
            return f'{self.source} used {self.ability} on {self.target} ({self.amount} hp)'
        if self.type == EventType.enemies_approach:
            return f'enemies approach'
        return 'invalid GameEvent'

    @property
    def target(self) -> str:
        if self._target is not None:
            return self._target
        raise ValueError()

    @target.setter
    def target(self, v: str) -> None:
        self._target = v

    @property
    def source(self) -> str:
        if self._source is not None:
            return self._source
        raise ValueError()

    @source.setter
    def source(self, v: str) -> None:
        self._source = v

    @property
    def item(self) -> str:
        if self._source is not None:
            return self._source
        raise ValueError()

    @item.setter
    def item(self, v: str) -> None:
        self._source = v

    @property
    def ability(self) -> str:
        if self._ability is not None:
            return self._ability
        raise ValueError()

    @ability.setter
    def ability(self, v: str) -> None:
        self._source = v

    @property
    def amount(self) -> int:
        if self._amount is not None:
            return self._amount
        raise ValueError()

    @amount.setter
    def amount(self, v: int) -> None:
        self._amount = v

    @property
    def encounter(self) -> int:
        if self._amount is not None:
            return self._amount
        raise ValueError()

    @amount.setter
    def encounter(self, v: int) -> None:
        self._amount = v

    @property
    def total(self) -> int:
        if self._total is not None:
            return self._total
        raise ValueError()

    @total.setter
    def total(self, v: int) -> None:
        self._total = v

    @property
    def damage(self) -> int:
        if self._amount is not None:
            return self._amount
        raise ValueError()

    @damage.setter
    def damage(self, v: int) -> None:
        self._amount = v
