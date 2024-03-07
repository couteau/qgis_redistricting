# -*- coding: utf-8 -*-
"""FieldList - manage lists of population or geography fields

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 *   This program is distributed in the hope that it will be useful, but   *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the          *
 *   GNU General Public License for more details. You should have          *
 *   received a copy of the GNU General Public License along with this     *
 *   program. If not, see <http://www.gnu.org/licenses/>.                  *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import annotations

from typing import (
    Generic,
    Iterator,
    List,
    TypeVar,
    Union
)

from .Field import Field

T = TypeVar("T", bound=Field)


class FieldList(Generic[T]):
    def __init__(self, fields: List[T] = None):
        self._fields: List[T] = fields or []

    def __getitem__(self, key) -> Union[T, FieldList[T]]:
        if isinstance(key, str):
            item = next((f for f in self._fields if f.fieldName == key), None)
            if item is None:
                raise KeyError()
            return item

        if isinstance(key, int):
            return self._fields[key]

        if isinstance(key, slice):
            return FieldList(self._fields[key])

        raise KeyError()

    def __delitem__(self, key: Union[int, slice]):
        del self._fields[key]

    def __contains__(self, item: Union[T, str]) -> bool:
        if isinstance(item, Field):
            return item in self._fields

        if isinstance(item, str):
            f = next((f for f in self._fields if f.fieldName == item), None)
            return f is not None

        if item is None:
            return False

        raise ValueError()

    def __bool__(self):
        return bool(self._fields)

    def append(self, item: T):
        self._fields.append(item)

    def insert(self, idx, item: T):
        self._fields.insert(idx, item)

    def extend(self, items: Union[FieldList[T], List[T]]):
        if not items:
            return
        self._fields.extend(items)

    def clear(self):
        del self[:]

    def remove(self, item: T):
        self._fields.remove(item)

    def move(self, idx1, idx2):
        if 0 <= idx1 < len(self._fields) and 0 <= idx2 < len(self._fields):
            item = self._fields[idx1]
            self._fields[idx1] = self._fields[idx2]
            self._fields[idx2] = item
        else:
            raise IndexError()

    def __iadd__(self, item) -> FieldList[T]:
        if isinstance(item, Field):
            self.append(item)
        elif isinstance(item, list):
            self.extend(item)
        else:
            raise ValueError()

        return self

    def __eq__(self, value) -> bool:
        if isinstance(value, FieldList):
            return self._fields == value._fields

        if isinstance(value, list):
            return self._fields == value

        raise ValueError()

    def __iter__(self) -> Iterator[T]:
        return iter(self._fields)

    def __len__(self) -> int:
        return len(self._fields)
