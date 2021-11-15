#!/usr/bin/env python3
from __future__ import annotations
from typing import Optional
import enum


class EventType(enum.Enum):
    monster_hit = 'monster_hit'
    player_hit = 'player_hit'
    get_gold = 'get_gold'
    get_item = 'get_item'
    get_exp = 'get_exp'


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
    ) -> None:
        self.type = typ
        self._target = target
        self._total = total
        self._source = source or item
        self._amount = amount or damage
        self._ability = ability

    def __str__(self) -> str:
        if self.type in (EventType.monster_hit, EventType.player_hit):
            return f'{self.source} used {self.ability} on {self.target} ({self.damage} damage)'
        if self.type == EventType.get_gold:
            return f'you found {self.amount} gold'
        if self.type == EventType.get_exp:
            return f'you got {self.amount} experience'
        if self.type == EventType.get_item:
            return f'you found an item: {self.item}'
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
