"""QGIS Redistricting Plugin - dict/list hybrid collection classes

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

import sys
from bisect import bisect_left, insort
from collections.abc import (
    Callable,
    Collection,
    Hashable,
    Iterable,
    Iterator,
    Mapping,
    MutableSequence,
    Set,
    Sized,
)
from operator import attrgetter
from typing import TYPE_CHECKING, Generic, Optional, SupportsIndex, TypeVar, Union, _GenericAlias, cast, overload

from .base import MISSING

if TYPE_CHECKING:
    from typing import Self

_K = TypeVar("_K", bound=Hashable)
_T = TypeVar("_T")
_DT = TypeVar("_DT")


def identity(x: _T) -> _K:
    return id(x)


class GenericKeyedList(_GenericAlias, _root=True):
    def __call__(self, *args, **kwargs):
        """override __call__ to tell the instance the type of the list elements
        where a parameterized class is invoked to create the instance"""
        if (
            len(args) < 4
            and "elem_type" not in kwargs
            and len(self.__args__) == 2
            and isinstance(self.__args__[1], type)
        ):
            kwargs["elem_type"] = self.__args__[1]

        return super().__call__(*args, **kwargs)


class ListDict(dict[_K, _T]):
    class Indexer(MutableSequence[_T]):
        def __init__(self, outer: "ListDict[_K, _T]"):
            self._outer = outer
            self._keys = outer._keys
            self._keys_getitem = self._keys.__getitem__
            self._outer_getitem = self._outer.__getitem__

        def __getitem__(self, index, /):
            if isinstance(index, slice):
                return ListDict({k: self._outer_getitem(k) for k in self._keys_getitem(index)})

            return self._outer_getitem(self._keys_getitem(index))

        def __setitem__(self, index, value, /):
            if isinstance(index, slice):
                raise ValueError("Cannot set a slice on a ListDict")

            self._outer[self._keys_getitem(index)] = value

        def __delitem__(self, index, /):
            if isinstance(index, slice):
                for i in index:
                    del self._outer[self._keys_getitem(i)]
            else:
                del self._outer[self._keys_getitem(index)]

        def insert(self, index: SupportsIndex, value: _T, /):
            return NotImplemented

        def index(self, value: _K):
            return self._keys.index(value)

    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self._keys = list[self.keys()]

    @property
    def ipos(self):
        return self.Indexer(self)

    def _addkey(self, key: _K) -> None:
        self._keys.append(key)

    def __setitem__(self, key: _K, value: _T):
        if key not in self:
            self._addkey(key)
        super().__setitem__(key, value)

    def __delitem__(self, key: _K):
        super().__delitem__(key)
        self._keys.remove(key)

    def __iter__(self):
        return iter(self._keys)

    def __repr__(self):
        return repr({k: self[k] for k in self._keys})


class SortedListDict(ListDict[_K, _T]):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self._keys.sort()

    def _addkey(self, key: _K):
        insort(self._keys, key)


class KeyedListMappingView(Sized):
    __slots__ = ("_mapping",)

    def __init__(self, mapping: "KeyedList[_K, _T]"):
        self._mapping: "KeyedList[_K, _T]" = mapping

    def __len__(self):
        return len(self._mapping)

    def __repr__(self):
        return "{0.__class__.__name__}({0._mapping!r})".format(self)

    __class_getitem__ = classmethod(_GenericAlias)


class KeyedListKeysView(KeyedListMappingView[_K, _T], Set[_K]):
    __slots__ = ()

    @classmethod
    def _from_iterable(cls, it):
        return set(it)

    def __contains__(self, key: _K) -> bool:
        return key in self._mapping._items

    def __iter__(self) -> Iterator[_K]:
        yield from self._mapping._keys


class KeyedListItemsView(KeyedListMappingView[_K, _T], Set[tuple[_K, _T]]):
    __slots__ = ()

    @classmethod
    def _from_iterable(cls, it):
        return set(it)

    def __contains__(self, item):
        key, value = item
        try:
            v = self._mapping.get(key)
        except KeyError:
            return False
        else:
            return v is value or v == value

    def __iter__(self) -> Iterator[tuple[_K, _T]]:
        for key in self._mapping._keys:
            yield (key, self._mapping._items_getitem(key))


class ValuesView(KeyedListMappingView[_K, _T], Collection[_T]):
    __slots__ = ()

    def __contains__(self, value):
        return value in self._mapping

    def __iter__(self):
        return iter(self._mapping)


class KeyedList(Generic[_K, _T], MutableSequence[_T]):
    def __init_subclass__(cls, *args, **kwargs):
        """set __args__ on subclass if baseclass is parameterized in subclass definition"""
        super().__init_subclass__(*args, **kwargs)
        if hasattr(cls, "__orig_bases__"):
            # find the right base class
            for c in cls.__orig_bases__:
                if isinstance(c, GenericKeyedList):
                    break
            else:
                return

            # ignore base classes that are still generic
            if len(c.__args__) == 2 and not isinstance(c.__args__[1], TypeVar):
                cls.__args__ = c.__args__

    def __class_getitem__(cls, args):
        return GenericKeyedList(cls, args)

    def __init__(
        self,
        iterable: Optional[Iterable[_T]] = None,
        *,
        key: Optional[Union[str, Callable[[_T], _K]]] = None,
        elem_type: Optional[type[_T]] = None,
    ):
        self._items: dict[_K, _T] = {}
        self._keys: list[_K] = []

        if key is None:
            if (
                elem_type is None
                and hasattr(self, "__args__")
                and isinstance(self.__args__, tuple)
                and len(self.__args__) == 2
                and isinstance(self.__args__[1], type)
            ):
                elem_type = self.__args__[1]

            if elem_type is not None and hasattr(elem_type, "__key__"):
                self._keyfunc = cast("Callable[[_T], _K]", elem_type.__key__)
            else:
                self._keyfunc = identity
        elif isinstance(key, str):
            self._keyfunc = cast("Callable[[_T], _K]", attrgetter(key))
        else:
            self._keyfunc = key

        self._items_getitem = self._items.__getitem__
        self._items_setitem = self._items.__setitem__
        self._items_delitem = self._items.__delitem__
        self._keys_getitem = self._keys.__getitem__
        self._keys_setitem = self._keys.__setitem__
        self._keys_delitem = self._keys.__delitem__
        self._keys_insert = self._keys.insert
        self._keys_append = self._keys.append

        if iterable is not None:
            if isinstance(iterable, Mapping):
                for k, v in iterable.items():
                    self.set(k, v)
            else:
                self.extend(iterable)

    def index(self, value: _T, start: SupportsIndex = 0, stop: SupportsIndex = sys.maxsize, /) -> int:
        key = self._keyfunc(value)
        return self._keys.index(key)

    def __iter__(self) -> Iterator[_T]:
        for k in self._keys:
            yield self._items_getitem(k)

    @overload
    def __getitem__(self, index: SupportsIndex) -> _T: ...

    @overload
    def __getitem__(self, index: slice) -> "Self[_K, _T]": ...

    def __getitem__(self, index):
        if isinstance(index, slice):
            instance = self.__class__(key=self._keyfunc)
            instance._keys.extend(self._keys_getitem(index))
            instance._items.update({k: self._items_getitem(k) for k in instance._keys})
            return instance

        return self._items_getitem(self._keys_getitem(index))

    @overload
    def __setitem__(self, index: SupportsIndex, value: _T) -> None: ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[_T]) -> None: ...

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            old_keys = self._keys_getitem(index)

            new_items = {}
            for v in value:
                key = self._keyfunc(v)
                if key in self._items and key not in old_keys:
                    raise KeyError("Cannot insert duplicate key in KeyedList")
                new_items[key] = v

            for key in old_keys:
                self._items_delitem(key)
            self._items.update(new_items)
            self._keys_setitem(index, new_items.keys())
        else:
            key = self._keyfunc(value)
            if key in self._items and self._keys_getitem(index) != key:
                raise KeyError("Cannot insert duplicate key in KeyedList")
            self._items_setitem(key, value)
            self._keys_setitem(index, key)

    @overload
    def __delitem__(self, index: SupportsIndex) -> None: ...

    @overload
    def __delitem__(self, index: slice) -> None: ...

    def __delitem__(self, index):
        old_keys = self._keys_getitem(index)
        self._keys_delitem(index)
        if isinstance(index, slice):
            for key in old_keys:
                self._items_delitem(key)
        else:
            self._items_delitem(old_keys)

    def insert(self, index: SupportsIndex, value: _T) -> None:
        key = self._keyfunc(value)
        if key in self._items:
            raise KeyError("Cannot insert duplicate key in KeyedList")
        self._keys_insert(index, key)
        self._items_setitem(key, value)

    def __len__(self):
        return len(self._items)

    def __contains__(self, value: _T):
        key = self._keyfunc(value)
        return key in self._items and self._items_getitem(key) == value

    def keys(self) -> KeyedListKeysView[_K, _T]:
        return KeyedListKeysView(self)

    def items(self) -> KeyedListItemsView[_K, _T]:
        return KeyedListItemsView(self)

    @overload
    def get(self, key: _K) -> _T: ...

    @overload
    def get(self, key: _K, default: _T) -> _T: ...

    @overload
    def get(self, key: _K, default: _DT) -> Union[_T, _DT]: ...

    def get(self, key, default=MISSING):
        if default is MISSING and key not in self._items:
            raise KeyError(str(key))

        return self._items.get(key, default)

    def set(self, key: _K, value: _T) -> None:
        if key != self._keyfunc(value):
            raise ValueError("Key doesn't match value")

        if key not in self._items:
            self._keys_append(key)

        self._items[key] = value

    def has(self, key: _K) -> bool:
        return key in self._items

    def __repr__(self):
        return f"{self.__class__.__name__}[{', '.join(repr(self._items[k]) for k in self._keys)}]"


class SortedKeyedList(KeyedList[_K, _T]):
    def __init__(
        self,
        iterable: Optional[Iterable[_T]] = None,
        *,
        key: Optional[Union[str, Callable[[_T], _K]]] = None,
        elem_type: Optional[type[_T]] = None,
    ):
        super().__init__(iterable, key=key, elem_type=elem_type)
        self._keys.sort()
        self._keys_setitem = self._notimplemented
        self._keys_append = self._appendkey
        self._keys_insert = self._insertkey

    def index(self, value: _T, start: SupportsIndex = 0, stop: SupportsIndex = sys.maxsize, /) -> int:
        key = self._keyfunc(value)
        i = bisect_left(self._keys, key)
        if i != len(self._keys) and self._keys[i] == key:
            return i
        raise ValueError("Value not found in KeyedList")

    def _notimplemented(self, index: SupportsIndex, key: _K):
        return NotImplemented

    def _appendkey(self, key: _K, /):
        insort(self._keys, key)

    def _insertkey(self, index: SupportsIndex, key: _K, /):
        if index != len(self._items):
            raise NotImplementedError()

        insort(self._keys, key)

    def __setitem__(self, index, value):
        raise NotImplementedError()

    def insert(self, index: SupportsIndex, value: _T):
        if index != len(self._items):
            raise NotImplementedError()

        super().insert(index, value)
