"""QGIS Redistricting Plugin - dict/list hybrid collection class

        begin                : 2024-09-15
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
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

import bisect
import sys
from collections.abc import Iterable, Iterator, Mapping, MutableMapping, MutableSequence, Sized
from copy import copy
from itertools import groupby
from operator import attrgetter, itemgetter
from types import GenericAlias
from typing import Callable, Generic, TypeVar, Union, overload

from qgis.PyQt.QtCore import QObject, pyqtSignal

_REPR_MAX_STRING_LENGTH = 23


def truncate_str(s: str):
    if len(s) > _REPR_MAX_STRING_LENGTH:
        return f"{s[:10]}...{s[-10:]}"

    return s


_T = TypeVar("_T")


class KeyedListView(Generic[_T], Sized):
    __slots__ = ("_reflist",)

    def __init__(self, reflist: "KeyedList[_T]"):
        self._reflist = reflist

    def __len__(self):
        return len(self._reflist)


class KeyedListKeyView(KeyedListView[_T]):
    __slots__ = ()

    def __iter__(self) -> Iterator[str]:
        yield from self._reflist._keys

    def __contains__(self, key: str):
        return key in self._reflist._items

    def __repr__(self):
        return f"KeyedListKeyView({repr(self._reflist._keys)})"


class KeyedListValueView(KeyedListView[_T]):
    __slots__ = ()

    def __iter__(self) -> Iterator[_T]:
        for k in self._reflist._keys:
            yield self._reflist._items[k]

    def __contains__(self, item: _T):
        return item in self._reflist._items.values()

    def __repr__(self):
        return f"KeyedListValueView([{
            truncate_str(', '.join(repr(self._reflist._items[k]) for k in self._reflist._keys))
        }])"

    __class_getitem__ = classmethod(GenericAlias)


class KeyedListItemsView(KeyedListView[_T]):
    __slots__ = ()

    def __iter__(self) -> Iterator[tuple[str, _T]]:
        for k in self._reflist._keys:
            yield (k, self._reflist._items[k])

    def __contains__(self, item: tuple[str, _T]):
        key, value = item
        try:
            v = self._reflist[key]
        except KeyError:
            return False

        return v is value or v == value

    def __repr__(self):
        return f"KeyedListItemsView([{
            truncate_str(', '.join(f'({k}, {repr(self._reflist._items[k])})' for k in self._reflist._keys))
        }])"


list_type_cache: dict[str, type] = {}


class KeyedList(Generic[_T], QObject):
    itemRemoved = pyqtSignal(int, "PyQt_PyObject")
    itemsRemoved = pyqtSignal(int, int, "PyQt_PyObject")
    itemAdded = pyqtSignal(int, "PyQt_PyObject")
    itemsAdded = pyqtSignal(int, int, "PyQt_PyObject")
    itemReplaced = pyqtSignal(int, int, "PyQt_PyObject", "PyQt_PyObject")
    itemsReplaced = pyqtSignal(int, int, "PyQt_PyObject", "PyQt_PyObject")
    itemMoved = pyqtSignal(int, int, "PyQt_PyObject")

    def __class_getitem__(cls, *args):
        generic = super().__class_getitem__(*args)
        if not all(isinstance(arg, TypeVar) for arg in args):
            name = repr(generic)
            if name not in list_type_cache:
                list_type_cache[name] = type(cls.__name__, (cls,), {"__args__": args})

            generic.__origin__ = list_type_cache[name]

        return generic

    @overload
    def __init__(self, key: Callable[[_T], str]): ...

    @overload
    def __init__(self, key: str): ...

    @overload
    def __init__(self, key: int): ...

    @overload
    def __init__(self, iterable: Union[Iterable[_T], Mapping[str, _T]], key: Callable[[_T], str]): ...

    @overload
    def __init__(self, iterable: Union[Iterable[_T], Mapping[str, _T]], key: str): ...

    @overload
    def __init__(self, iterable: Union[Iterable[_T], Mapping[str, _T]], key: int): ...

    def __init__(self, iterable=None, key=None):
        super().__init__()

        if isinstance(iterable, (Callable, str, int)):
            key = iterable
            iterable = None

        if key is None:
            if (
                hasattr(type(self), "__args__")
                and len(type(self).__args__) > 0
                and hasattr(type(self).__args__[0], "__key__")
            ):
                key = type(self).__args__[0].__key__
            else:
                raise ValueError("Key function must be supplied to KeyedList")

        if isinstance(key, str):
            key = attrgetter(key)
        elif isinstance(key, int):
            key = itemgetter(key)
        elif isinstance(key, type) and hasattr(key, "__key__"):
            key = key.__key__

        self._keyfunc: Callable[[_T], str] = key

        if iterable is not None:
            if isinstance(iterable, Mapping):
                self._items: dict[str, _T] = dict(iterable)
            else:
                self._items: dict[str, _T] = {self._keyfunc(i): i for i in iterable}
        else:
            self._items = {}

        self._keys = list(self._items.keys())

    def __len__(self):
        return len(self._items)

    def __repr__(self):
        return f"{self.__class__.__name__}([{truncate_str(', '.join(repr(self._items[d]) for d in self._keys))}])"

    def __copy__(self):
        return type(self)(self._items, self._keyfunc)

    def __reversed__(self):
        inst = type(self)(self._keyfunc)
        inst._items = self._items  # pylint: disable=attribute-defined-outside-init
        inst._keys = reversed(self._keys)  # pylint: disable=attribute-defined-outside-init
        return inst

    def keys(self) -> KeyedListKeyView[_T]:
        return KeyedListKeyView(self)

    def values(self) -> KeyedListValueView[_T]:
        return KeyedListValueView(self)

    def items(self) -> KeyedListItemsView[_T]:
        return KeyedListItemsView(self)

    def _getranges(self, indices):
        """return a list of ranges of indices from a list of indices"""
        gb = groupby(enumerate(sorted(indices)), key=lambda x: x[0] - x[1])
        groups = [list(g[1]) for g in gb]
        return (range(s[0][1], s[-1][1] + 1) for s in groups)

    def _addkey(self, key: str) -> int:
        if key in self._keys:
            raise KeyError("Key already in list")
        self._keys.append(key)
        return len(self._keys) - 1

    def _addkeys(self, keys: Iterable[str]):
        newkeys = copy(self._keys)
        newkeys.extend(keys)
        if len(set(newkeys)) != len(newkeys):
            raise KeyError("Keys overlap")

        start = len(self._keys)
        self._keys = newkeys
        stop = len(self._keys)

        return (range(start, stop),)

    def _insertkey(self, index: int, key: str) -> int:
        if key in self._keys:
            raise KeyError("Key already in list")
        self._keys.insert(index, key)
        return index

    def _replacekey(self, index: int, key: str) -> int:
        if key in self._keys and self._keys.index(key) != index:
            raise KeyError("Key already in list")

        self._keys[index] = key
        return index

    def _replacekeys(self, index: slice, keys: Iterable[str]):
        newkeys = copy(self._keys)
        newkeys[index] = keys

        if len(set(newkeys)) != len(newkeys):
            raise KeyError("Keys overlap")

        self._keys = newkeys
        return (range(*index.indices(len(self._keys))),)

    def _updatekeys(self, keys: Iterable[str]):
        updatedkeys = []
        start = len(self._keys)
        for k in keys:
            if k in self._keys:
                updatedkeys.append(self._keys.index(k))
            else:
                self._keys.append(k)

        return self._getranges(updatedkeys), (range(start, len(self._keys)),)

    def _replaceitem(self, index: int, oldkey: str, item: _T):
        newkey = self._keyfunc(item)
        newindex = self._replacekey(index, newkey)
        olditem = self._items[oldkey]
        del self._items[oldkey]
        self._items[newkey] = item

        self.itemReplaced.emit(newindex, index, item, olditem)

    def _additem(self, key, item):
        self._addkey(key)
        self._items[key] = item
        self.itemAdded.emit(self._keys.index(key), item)

    def _setitembykey(self, oldkey: str, item: _T):
        if oldkey in self._keys:
            self._replaceitem(self._keys.index(oldkey), oldkey, item)
        else:
            self._additem(oldkey, item)

    def _setitembyindex(self, index: int, item: _T):
        self._replaceitem(index, self._keys[index], item)

    def _replaceitems(self, index: slice, items: Iterable[_T]):
        value = {self._keyfunc(v): v for v in items}

        oldkeys = self._keys[index]
        oldrange = range(*index.indices(len(self._keys)))
        olditems = {k: self._items[k] for k in oldkeys}

        newranges = self._replacekeys(index, value.keys())

        if len(olditems) > 0:
            self._items = {k: v for k, v in self._items.items() if k not in oldkeys}
            self.itemsRemoved.emit(oldrange.start, oldrange.stop - 1, olditems)

        if len(value) > 0:
            self._items.update(value)
            for g in newranges:
                self.itemsAdded.emit(g.start, g.stop - 1, (value[self._keys[i]] for i in g))

    def _delitem(self, index: Union[str, int]):
        if isinstance(index, int):
            key = self._keys.pop(index)
        else:
            key = index
            index = self._keys.index(key)
            del self._keys[index]

        item = self._items[key]
        del self._items[key]

        self.itemRemoved.emit(index, item)

    def _delitems(self, index: slice):
        r = range(*index.indices(len(self._items)))
        keys = self._keys[index]
        items = [self._items[k] for k in keys]

        del self._keys[index]
        self._items = {k: v for k, v in self._items.items() if k not in keys}

        self.itemsRemoved(r.start, r.stop - 1, items)

    @overload
    def __getitem__(self, index: int) -> _T: ...

    @overload
    def __getitem__(self, index: str) -> _T: ...

    @overload
    def __getitem__(self, index: slice) -> Iterable[_T]: ...

    def __getitem__(self, index):
        if isinstance(index, slice):
            return type(self)([self._items[i] for i in self._keys[index]], self._keyfunc)

        if isinstance(index, int):
            return self._items[self._keys[index]]

        if isinstance(index, str):
            return self._items[index]

        raise IndexError("Index must be string, integer, or slice")

    @overload
    def __setitem__(self, index: int, value: _T): ...

    @overload
    def __setitem__(self, index: str, value: _T): ...

    @overload
    def __setitem__(self, index: slice, value: Union[Iterable[_T], Mapping[str, _T]]): ...

    def __setitem__(self, index: Union[int, str, slice], value: Union[_T, Iterable[_T]]):
        if isinstance(index, slice):
            if not isinstance(value, Iterable):
                raise TypeError("can only assign an iterable")

            if isinstance(value, Mapping):
                value = value.values()

            self._replaceitems(index, value)
        elif isinstance(index, int):
            if index < 0 or index >= len(self._keys):
                raise IndexError("Index out of range")

            self._setitembyindex(index, value)
        elif isinstance(index, str):
            if index != self._keyfunc(value):
                raise ValueError("Item key doesn't match index")

            self._setitembykey(index, value)
        else:
            raise IndexError("invalid index")

    @overload
    def __delitem__(self, index: int): ...

    @overload
    def __delitem__(self, index: str): ...

    @overload
    def __delitem__(self, index: slice): ...

    def __delitem__(self, index: Union[int, str, slice]):
        if isinstance(index, (str, int)):
            self._delitem(index)
        elif isinstance(index, slice):
            self._delitems(index)
        else:
            raise IndexError()

    def __contains__(self, item: Union[str, _T]):
        if isinstance(item, str):
            return item in self._items

        return item in self._items.values()

    def __eq__(self, value: "KeyedList") -> bool:
        if not isinstance(value, KeyedList):
            return False
        return self._keys == value._keys and self._items == value._items

    def __iter__(self) -> Iterator[_T]:
        for k in self._keys:
            yield self._items[k]

    def __iadd__(self, other: Union[_T, Iterable[_T], Mapping[str, _T]]):
        if not isinstance(other, Iterable):
            self.append(other)
        else:
            self.extend(other)
        return self

    def __add__(self, other: Union[_T, Iterable[_T], Mapping[str, _T]]):
        newlist = copy(self)
        if not isinstance(other, Iterable):
            newlist.append(other)
        else:
            newlist.extend(other)

        return newlist

    def append(self, item: _T):
        key = self._keyfunc(item)
        self._additem(key, item)

    def insert(self, index: int, item: _T):
        key = self._keyfunc(item)
        index = self._insertkey(index, key)
        self._items[key] = item
        self.itemAdded.emit(index, key)

    def move(self, from_index: int, to_index: int):
        if 0 <= from_index < len(self._items) and 0 <= to_index < len(self._items):
            self._keys[to_index:to_index] = self._keys.pop(from_index)
            self.itemMoved.emit(from_index, to_index, self._items[self._keys[to_index]])
        else:
            raise IndexError()

    def extend(self, iterable: Union[Iterable[_T], Mapping[str, _T]]):
        if isinstance(iterable, Mapping):
            iterable = iterable.values()

        if len(iterable) == 0:
            return

        items = {self._keyfunc(item): item for item in iterable}
        newranges = self._addkeys(items.keys())
        self._items.update(items)
        if len(newranges) == 1:
            self.itemsAdded.emit(newranges[0].start, newranges[0].stop, items.values())
        else:
            for g in newranges:
                self.itemsAdded.emit(g.start, g.stop, (self._items[self._keys[i]] for i in g))

    def update(self, values: Union[Iterable[_T], Mapping[str, _T]]):
        if isinstance(values, Mapping):
            values = values.values()

        values = {self._keyfunc(v): v for v in values}
        olditems = {k: self._items[k] for k in values if k in self._items}

        updateranges, newranges = self._updatekeys(values.keys())
        self._items.update(values)
        for g in updateranges:
            self.itemsReplaced.emit(
                g.start, g.stop, (self._items[self._keys[i]] for i in g), (olditems[self._keys[i]] for i in g)
            )
        for g in newranges:
            if g:
                self.itemsAdded.emit(g.start, g.stop, (self._items[self._keys[i]] for i in g))

    def index(self, item: _T, start=0, stop=sys.maxsize):
        key = self._keyfunc(item)
        return self._keys.index(key, start, stop)

    def remove(self, item: _T):
        key = self._keyfunc(item)
        if key not in self._items:
            raise ValueError(f"Item {key} not in Collection")

        self._delitem(key)

    def clear(self):
        self._keys.clear()
        self._items.clear()


MutableSequence.register(KeyedList)
MutableMapping.register(KeyedList)


class SortedKeyedList(KeyedList[_T]):
    def __init__(self, iterable=None, key=None):
        super().__init__(iterable, key)
        self._keys = sorted(self._keys)

    def _addkey(self, key: str) -> int:
        if key in self._keys:
            raise KeyError("Key already in list")
        index = bisect.bisect(self._keys, key)
        self._keys.insert(index, key)
        return index

    def _addkeys(self, keys: Iterable[str]):
        if set(keys) & set(self._keys):
            raise KeyError("Keys overlap")

        indices = []
        for k in keys:
            index = bisect.bisect(self._keys, k)
            self._keys.insert(index, k)
            indices.append(index)

        return self._getranges(indices)  # pylint: disable=no-member

    def _insertkey(self, index: int, key: str) -> int:
        raise NotImplementedError("Cannot insert key into sorted list at arbitrary point")

    def _replacekey(self, index: int, key: str) -> int:
        if key in self._keys and bisect.bisect_left(self._keys, key) != index:
            raise KeyError("Key already in list")

        del self._keys[index]
        newindex = bisect.bisect(self._keys, key)
        self._keys.insert(self._keys, key)
        return newindex

    def _replacekeys(self, index: slice, keys: Iterable[str]):
        newkeys = copy(self._keys)
        del newkeys[index]

        indices = []
        for k in keys:
            if k in newkeys:
                raise KeyError("Keys overlap")

            index = bisect.bisect(self._keys, k)
            newkeys.insert(index, k)
            indices.append(index)

        return self._getranges(indices)  # pylint: disable=no-member

    def _updatekeys(self, keys: Iterable[str]):
        updateindices = []
        newindices = []
        for k in keys:
            if k in self._keys:
                updateindices.append(bisect.bisect_left(self._keys, k))
            else:
                index = bisect.bisect(self._keys, k)
                self._keys.insert(index, k)
                newindices.append(index)

        return self._getranges(updateindices), self._getranges(newindices)  # pylint: disable=no-member

    def _setitembyindex(self, index, item):
        raise NotImplementedError("Cannot set item at arbitrary point in sorted list")

    def move(self, idx1, idx2):
        raise NotImplementedError("Cannot move items in a sorted list")


MutableSequence.register(SortedKeyedList)
MutableMapping.register(SortedKeyedList)
