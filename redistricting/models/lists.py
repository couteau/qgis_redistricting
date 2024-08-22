
import bisect
import sys
from copy import copy
from types import GenericAlias
from typing import (
    Any,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    MutableSequence,
    Self,
    Sized,
    TypeVar,
    Union,
    overload
)

from .base import (
    MISSING,
    Factory
)

T = TypeVar("T")


def key(item: T, default=MISSING) -> str:
    if hasattr(item, "__key__"):
        return item.__key__()

    if default is not MISSING:
        return default

    raise ValueError(f"Could not determine key of Item {item!r}")


class KeyedListView(Generic[T], Sized):
    __slots__ = ("_list",)

    def __init__(self, reflist: "KeyedList[T]"):
        self._list = reflist

    def __len__(self):
        return len(self._list)


class KeyedListKeyView(KeyedListView):
    __slots__ = ()

    def __iter__(self) -> Iterator[str]:
        yield from self._list._keys

    def __contains__(self, key: str):  # pylint: disable=redefined-outer-name
        return key in self._list._items

    def __repr__(self):
        return f"KeyedListKeyView({repr(self._list._keys)})"


class KeyedListValueView(KeyedListView[T]):
    __slots__ = ()

    def __iter__(self) -> Iterator[T]:
        for k in self._list._keys:
            yield self._list._items[k]

    def __contains__(self, item: T):
        return item in self._list._items.values()

    def __repr__(self):
        return f"KeyedListValueView([{', '.join(repr(self._list._items[k]) for k in self._list._keys)}])"

    __class_getitem__ = classmethod(GenericAlias)


class KeyedListItemsView(KeyedListView[T]):
    __slots__ = ()

    def __iter__(self) -> Iterator[tuple[str, T]]:
        for k in self._list._keys:
            yield (k, self._list._items[k])

    def __contains__(self, item):
        item_key, value = item
        try:
            v = self._list[item_key]
        except KeyError:
            return False

        return v is value or v == value

    def __repr__(self):
        return f"KeyedListItemsView([{', '.join(f'({k}, {repr(self._list._items[k])})' for k in self._list._keys)}])"


class KeyedList(Generic[T]):
    """Sequence-Mapping hybrid, indexible by string or integer"""

    @overload
    def __init__(self):
        ...

    @overload
    def __init__(self, iterable: Union[Iterable[T], Mapping[str, T]]):
        ...

    def __init__(self, iterable=None):
        if iterable is not None:
            if isinstance(iterable, Mapping):
                self._items = {k: v for k, v in iterable.items()}
            elif isinstance(iterable, Iterable) and not isinstance(iterable, (str, bytes)):
                self._items = {key(v): v for v in iterable}
            else:
                raise TypeError(f"Cannot create KeyedList from {iterable}")
            self._keys = list(self._items.keys())
        else:
            self._items: dict[str, T] = {}
            self._keys = []

    def __repr__(self):
        return f"{self.__class__.__name__}([{', '.join(repr(self._items[d]) for d in self._keys)}])"

    def __copy__(self):
        inst = type(self)()
        inst._keys = self._keys.copy()
        inst._items = self._items.copy()
        return inst

    @overload
    def __getitem__(self, index: int) -> T:
        ...

    @overload
    def __getitem__(self, index: str) -> T:
        ...

    @overload
    def __getitem__(self, index: slice) -> Iterable[T]:
        ...

    @overload
    def __getitem__(self, index: tuple[Union[int, str], str]) -> Any:
        ...

    @overload
    def __getitem__(self, index: tuple[slice, str]) -> Iterable[Any]:
        ...

    def __getitem__(self, index: Union[int, str, slice, tuple[Union[int, str, slice], str]]) -> Union[T, Self, Any]:
        if isinstance(index, tuple):
            index, field = index
            item = self[index]
            if isinstance(item, Iterable):
                return (i[field] for i in item)

            return item[field]

        if isinstance(index, str):
            return self._items[index]

        if isinstance(index, int):
            return self._items[self._keys[index]]

        if isinstance(index, slice):
            # pylint: disable=attribute-defined-outside-init
            inst = copy(self)
            inst._keys = self._keys[index]
            inst._items = {k: self._items[k] for k in inst._keys}
            return inst

        raise IndexError()

    @overload
    def __setitem__(self, index: int, value: T):
        ...

    @overload
    def __setitem__(self, index: str, value: T):
        ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[T]):
        ...

    def __setitem__(self, index: Union[int, str, slice], value: Union[T, Iterable[T]]):
        if isinstance(index, slice):
            oldkeys = self._keys[index]
            if isinstance(value, Mapping):
                if any(key(v, k) != k for k, v in value.items()):
                    raise ValueError("Item key doesn't match index")
            elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
                value = {
                    key(item, oldkeys[i] if i < len(oldkeys) else MISSING): item
                    for i, item in enumerate(value)
                }
            else:  # value is a scalar
                r = range(*index.indices(len(self._items)))
                # pylint: disable-next=invalid-sequence-index
                default = MISSING if len(r) == 0 else self._keys[r.start]
                value = {
                    key(value, default): value
                }

            for k in value.keys():
                if k in self._items and k not in oldkeys:
                    raise ValueError("Duplicate key(s)")

            self._delitems(oldkeys)
            self._setitems(index, value)
        else:
            if isinstance(index, str):
                item_key = index
                if item_key != key(value, item_key):
                    raise ValueError("Item key doesn't match index")

                if item_key not in self._items:
                    index = slice(len(self._keys), len(self._keys))
                    self._setitems(index, {item_key: value})
                    return

                index = self._keys.index(index)
            else:
                item_key = key(value, self._keys[index])
                if item_key in self._items and item_key != self._keys[index]:
                    raise KeyError("Key already in list")

            if index < 0 or index >= len(self._keys):
                raise IndexError("Index out of range")

            if item_key in self._items:
                self._delitem(item_key)

            self._setitem(index, item_key, value)

    @overload
    def __delitem__(self, index: int):
        ...

    @overload
    def __delitem__(self, index: str):
        ...

    @overload
    def __delitem__(self, index: slice):
        ...

    def __delitem__(self, index: Union[int, str, slice]):
        if isinstance(index, (str, int)):
            if isinstance(index, int):
                index = self._keys.pop(index)
            else:
                self._keys.remove(index)
            self._delitem(index)
        elif isinstance(index, slice):
            removed = self._keys[index]
            del self._keys[index]
            self._delitems(removed)
        else:
            raise IndexError()

    def __len__(self):
        return len(self._items)

    def __contains__(self, item: Union[str, T]):
        if isinstance(item, str):
            return item in self._items

        return item in self._items.values()

    def __reversed__(self):
        inst = type(self)()
        inst._items = self._items  # pylint: disable=attribute-defined-outside-init
        inst._keys = reversed(self._keys)  # pylint: disable=attribute-defined-outside-init
        return inst

    def __eq__(self, value: "KeyedList") -> bool:
        if not isinstance(value, KeyedList):
            return False
        return self._keys == value._keys and self._items == value._items

    def __iter__(self) -> Iterator[T]:
        for k in self._keys:
            yield self._items[k]

    def keys(self) -> KeyedListKeyView:
        return KeyedListKeyView(self)

    def values(self) -> KeyedListValueView:
        return KeyedListValueView(self)

    def items(self) -> KeyedListItemsView:
        return KeyedListItemsView(self)

    def index(self, item: T, start=0, stop=sys.maxsize):
        item_key = key(item, None)
        if item_key is None:
            for k, v in self._items.items():
                if v == item:
                    item_key = k
                    break
            else:
                raise ValueError(f"{item!r} is not in list")

        return self._keys.index(item_key, start, stop)

    def __iadd__(self, other: Union[Iterable[T], Mapping[str, T]]):
        if not isinstance(other, Iterable):
            return NotImplemented
        self.extend(other)
        return self

    def __add__(self, other: Union[Iterable[T], Mapping[str, T]]):
        if not isinstance(other, Iterable):
            return NotImplemented
        newlist = type(self)(self)
        newlist.extend(other)
        return newlist

    def __radd__(self, other: Union[Iterable[T], Mapping[str, T]]):
        if not isinstance(other, Iterable):
            return NotImplementedError()
        newlist = type(self)(other)
        newlist.extend(self)
        return newlist

    def __or__(self, other: Union[Iterable[T], Mapping[str, T]]) -> Self:
        if not isinstance(other, Mapping):
            other = {key(v): v for v in other}

        newlist = type(self)(self)
        newlist._keys.extend(other.keys() - self._items.keys())
        newlist._items.update(other)
        return newlist

    def __ior__(self, other: Union[Iterable[T], Mapping[str, T]]):
        if not isinstance(other, Mapping):
            other = {key(v): v for v in other}

        self._keys.extend(other.keys() - self._items.keys())
        self._items.update(other)

    def __lshift__(self, item) -> Self:
        self.append(item)
        return self

    def append(self, item: T):
        item_key = key(item)
        if item_key in self._items:
            raise KeyError(f"Key {item_key!r} already exists in list")

        index = slice(len(self._keys), len(self._keys))
        self._setitems(index, {item_key: item})

    def extend(self, values: Union[Iterable[T], Mapping[str, T]]):
        if not isinstance(values, Mapping):
            values = {key(v): v for v in values}

        dups = self._items.keys() & values.keys()
        if dups:
            raise KeyError(f"{len(dups)} keys already exists in list: {dups!r}")

        index = slice(len(self._keys), len(self._keys))
        self._setitems(index, values)

    def insert(self, index: int, item: T):
        item_key = key(item)
        if item_key in self._items:
            raise KeyError(f"Keys {item_key} already exists in list")

        index = slice(index, index)
        self._setitems(index, {item_key: item})

    def remove(self, item: T):
        item_key = key(item, None)
        if item_key is None:
            for item_key, v in self._items.items():
                if v == item:
                    break
            else:
                raise ValueError("Item {item!r} not in Collection")
        else:
            if item_key not in self._items:
                raise ValueError("Item {item!r} not in Collection")

        self._keys.remove(item_key)
        self._delitem(item_key)

    def move(self, idx1: int, idx2: int):
        if 0 <= idx1 < len(self._items) and 0 <= idx2 < len(self._items):
            self._keys[idx2:idx2] = self._keys.pop(idx1)
        else:
            raise IndexError()

    def clear(self):
        self._keys.clear()
        self._items.clear()

    def _delitem(self, key: str):  # pylint: disable=redefined-outer-name
        del self._items[key]

    def _delitems(self, keys: Iterable[str]):
        for k in keys:
            self._delitem(k)

    def _setitem(self, index: int, key: str, item: T):  # pylint: disable=redefined-outer-name
        self._keys[index] = key
        self._items[key] = item

    def _setitems(self, index: slice, value: Mapping[str, T]):
        self._items.update(value)
        self._keys[index] = value.keys()


MutableSequence.register(KeyedList)
MutableMapping.register(KeyedList)


class SortedKeyedList(KeyedList[T]):
    def __init__(self, iterable=None):
        super().__init__(iterable)
        self._keys = sorted(self._items.keys())

    def append(self, item: T):
        item_key = key(item)
        if item_key in self._items:
            raise KeyError(f"Key {item_key!r} already exists in list")

        bisect.insort(self._keys, item_key)
        self._items[item_key] = item

    def extend(self, values: Union[Iterable[T], Mapping[str, T]]):
        if not isinstance(values, Mapping):
            values = {key(v): v for v in values}

        dups = self._items.keys() & values.keys()
        if dups:
            raise KeyError(f"{len(dups)} keys already exists in list: {dups!r}")

        for k in values.keys():
            bisect.insort(self._keys, k)
        self._items.update(values)

    def _raise_not_impl_error(self, func_name):
        raise NotImplementedError(f"{func_name} not implemented for sorted list")

    def __setitem__(self, index: str, value: T):
        if isinstance(index, str):
            super().__setitem__(index, value)
        else:
            self._raise_not_impl_error("Indexed assignment")

    def __or__(self, other: Union[Iterable[T], Mapping[str, T]]):
        newlist = super().__or__(other)
        newlist._keys = sorted(newlist._keys)

    def __ior__(self, other: Union[Iterable[T], Mapping[str, T]]):
        super().__ior__(other)
        self._keys = sorted(self._keys)

    def insert(self, index, item):
        self._raise_not_impl_error("Insertion")

    def move(self, idx1, idx2):
        self._raise_not_impl_error("Move item")


KeyedListFactory = Factory(KeyedList, False)
SortedKeyedListFactory = Factory(SortedKeyedList, False)
