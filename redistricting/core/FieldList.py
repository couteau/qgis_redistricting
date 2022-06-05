# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FieldList - manage lists of population or geography fields
                              -------------------
        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import annotations

from typing import Iterator, List, Union
from qgis.PyQt.QtCore import QObject, pyqtSignal

from .Field import Field, DataField


class FieldList(QObject):
    fieldAdded = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject', int)
    fieldRemoved = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject', int)
    fieldMoved = pyqtSignal('PyQt_PyObject', int, int)

    def __init__(self, parent: QObject = None, fields: List[Union[Field, DataField]] = None):
        super().__init__(parent)
        self._fields: List[Field] = fields or []
        for field in self._fields:
            field.setParent(self)

    def __getitem__(self, key) -> Union[Field, DataField, FieldList]:
        if isinstance(key, str):
            item = next((f for f in self._fields if f.fieldName == key), None)
            if item is None:
                raise KeyError()
            return item

        if isinstance(key, int):
            return self._fields[key]

        if isinstance(key, slice):
            return FieldList(self.parent(), self._fields[key])

        raise KeyError()

    def __delitem__(self, key: Union[int, slice]):
        if isinstance(key, slice):
            index = key.start
            fields = self._fields[key]
        else:
            fields = [self._fields[key]]
            index = self._fields.index(fields[0])
        del self._fields[key]
        for f in fields:
            f.setParent(None)
        self.fieldRemoved.emit(self, fields[0] if len(fields) == 1 else fields, index)

    def __contains__(self, item) -> bool:
        if isinstance(item, Field):
            return item in self._fields

        if isinstance(item, str):
            f = next((f for f in self._fields if f.fieldName == item), None)
            return f is not None

        raise ValueError()

    def append(self, item: Union[Field, DataField]):
        item.setParent(self)
        self._fields.append(item)
        self.fieldAdded.emit(self, item, len(self._fields) - 1)

    def insert(self, idx, item: Union[Field, DataField]):
        item.setParent(self)
        self._fields.insert(idx, item)
        self.fieldAdded.emit(self, item, idx)

    def extend(self, items: List[Union[Field, DataField]]):
        if not items:
            return
        self._fields.extend(items)
        for f in items:
            f.setParent(self)
        self.fieldAdded.emit(self, items, self._fields.index(items[0]))

    def clear(self):
        del self[:]

    def remove(self, item: Union[Field, DataField]):
        if item in self._fields:
            item.setParent(None)
            i = self._fields.index(item)
            self._fields.remove(item)
            self.fieldRemoved.emit(self, item, i)
            return

        raise ValueError()

    def move(self, idx1, idx2):
        if 0 <= idx1 < len(self._fields) and 0 <= idx2 < len(self._fields):
            item = self._fields[idx1]
            self._fields[idx1] = self._fields[idx2]
            self._fields[idx2] = item
            self.fieldMoved.emit(self, idx1, idx2)
        else:
            raise IndexError()

    def __iadd__(self, item) -> FieldList:
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

    def __iter__(self) -> Iterator[Union[Field, DataField]]:
        return iter(self._fields)

    def __len__(self) -> int:
        return len(self._fields)
