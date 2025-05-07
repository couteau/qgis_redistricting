"""QGIS Redistricting Plugin - dataclass-like field and property classes

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

import inspect
import math
import numbers
import sys
from collections.abc import Iterable, MutableSequence
from copy import copy
from enum import Enum
from reprlib import recursive_repr
from types import GenericAlias
from typing import (  # pylint: disable=no-name-in-module
    Annotated,
    Any,
    Callable,
    Generic,
    Literal,
    Optional,
    Self,
    TypeVar,
    Union,
    _AnnotatedAlias,
    _BaseGenericAlias,
    _GenericAlias,
    _strip_annotations,
    _UnionGenericAlias,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from qgis.PyQt.QtCore import pyqtSignal

from .serialization import (
    DeserializerFunction,
    SerializerFunction,
    SimpleDeserializeFunction,
    SimpleSerializeFunction,
    wrap_simple_deserializer,
    wrap_simple_serializer,
)

# pylint: disable=redefined-builtin


class _MISSING_TYPE:
    def __bool__(self):
        return False


MISSING = _MISSING_TYPE()


def get_real_type(t: type):
    if isinstance(t, _AnnotatedAlias):
        v = get_args(t)[1]
    else:
        v = None

    t = _strip_annotations(t)
    if isinstance(t, (_GenericAlias, GenericAlias)) and not isinstance(t, _UnionGenericAlias):
        args = get_args(t)
        t = get_origin(t)
        if t is Literal:
            t = type(args[0])

    return t, v


def type_name(t: type):
    if isinstance(t, _GenericAlias):
        if isinstance(t, _UnionGenericAlias):
            if t.__name__ == "Optional":
                return f"{get_args(t)[0].__name__} or None"
            return " or ".join(a.__name__ for a in get_args(t))

        t = get_origin(t)

    return repr(t.__name__)


def coerce_type(tp: Union[type, tuple[type]], value: Any, default: Any = MISSING) -> Any:
    if tp is Any or isinstance(value, tp):
        return value

    # don't try to coerce MISSING
    if value is MISSING:
        raise TypeError("cannot assign MISSING to instance attribute")

    if isinstance(tp, type):
        tp = (tp,)

    for t in tp:
        if issubclass(t, MutableSequence) and isinstance(value, Iterable):
            return value

        # try to coerce numeric types (but not bool)
        if issubclass(t, numbers.Number) and t is not bool:
            try:
                v = t(value)
                if v == value:  # if coercion changes value, fail (e.g., int(1.5))
                    return v
            except (ValueError, TypeError):
                pass

    # ok to set to default value even if default value is not of the appropriate type
    if value == default:
        return value

    raise TypeError(f"value {value!r} cannot be converted to {' or '.join(type_name(t) for t in tp)}")


_T = TypeVar("_T")


class Factory(Generic[_T]):
    """Factory class for wrapping default factory functions that take the instance as a parameter"""

    def __init__(
        self, factory: Union[Callable[[], _T], Callable[[Any], _T]], with_owner: bool = True, defer: bool = False
    ):
        """Constructor for Factory class for initializing model attributes

        Args:
            factory (Callable): The factory function wrapped by this Factory instance.
            with_owner (bool, optional): Whether the factory function takes the instance
                                         as an argument. Defaults to True.
            defer (bool, optional): Whether the factory should be called after all other
                                    instance attributes have been set. Defaults to False.
        """
        self.factory = factory
        self.with_owner = with_owner
        self.defer = defer

    def __call__(self, owner) -> _T:
        if self.with_owner:
            return self.factory(owner)

        return self.factory()


def not_empty(instance=None, value=None):
    if instance is None and value is None:
        return not_empty

    if not isinstance(value, str) or value != "":
        return value

    raise ValueError("Value must not be empty")


def isidentifier(instance=None, value=None):  # pylint: disable=unused-argument
    if isinstance(value, str) and value != "" and not value.isidentifier():
        raise ValueError("Value must be an identifier")

    return value


class in_range:
    def __init__(self, minValue=-math.inf, maxValue=math.inf):
        self.min = minValue
        self.max = maxValue

    def __call__(self, instance, value):
        if self.min.__eq__(value) is NotImplemented:
            raise TypeError("Range and value are incompatible types")

        if not self.min <= value <= self.max:
            raise ValueError(f"Value must be between {self.min} and {self.max}")

        return value


class InitVar:
    __slots__ = ("type",)

    def __init__(self, t):
        self.type = t

    def __repr__(self):
        if isinstance(self.type, type):
            tname = self.type.__name__
        else:
            tname = repr(self.type)
        return f"InitVar[{tname}]"

    def __class_getitem__(cls, t):
        return InitVar(t)


class PrivateVar:
    __slots__ = ("type",)

    def __init__(self, t):
        self.type = t

    def __repr__(self):
        if isinstance(self.type, type):
            tname = self.type.__name__
        else:
            tname = repr(self.type)
        return f"PrivateVar[{tname}]"

    def __class_getitem__(cls, t):
        return PrivateVar(t)


class FieldType(Enum):
    FIELD = 0
    INIT_VAR = 1
    CLASS_VAR = 2


class Field:
    def __init__(  # noqa: PLR0913 # pylint: disable=R0913, R0917
        self,
        default: Any = MISSING,
        factory: Union[Callable[[], Any], Callable[[Any], Any]] = MISSING,
        init: bool = True,
        repr: bool = True,
        hash: bool = None,
        compare: bool = True,
        serialize: bool = True,
        serializer: Union[SimpleSerializeFunction[_T], SerializerFunction[_T]] = None,
        deserializer: Union[SimpleDeserializeFunction[_T], DeserializerFunction[_T]] = None,
        kw_only: bool = MISSING,
    ):
        self.name = None
        self.type = Any
        self.default = default
        self.default_factory = factory
        self.init = init
        self.repr = repr
        self.hash = hash
        self.compare = compare
        self.serialize = serialize

        if serializer is not None and len(inspect.signature(serializer).parameters) == 1:
            self.fserialize = wrap_simple_serializer(serializer)
        else:
            self.fserialize = serializer

        if deserializer is not None and len(inspect.signature(deserializer).parameters) == 1:
            self.fdeserialize = wrap_simple_deserializer(deserializer)
        else:
            self.fdeserialize = deserializer

        self.kw_only = kw_only
        self._field_type = FieldType.FIELD

    def __set_name__(self, owner, name: str):
        self.name = name
        self.type = get_type_hints(owner).get(name, Any)

    @recursive_repr()
    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"name={self.name!r},"
            f"type={self.type!r},"
            f"default={self.default!r},"
            f"default_factory={self.default_factory!r},"
            f"init={self.init!r},"
            f"repr={self.repr!r},"
            f"hash={self.hash!r},"
            f"compare={self.compare!r},"
            f"serialize={self.serialize},"
            f"kw_only={self.kw_only!r}"
            ")"
        )

    def __copy__(self):
        newinst = type(self)(
            self.default,
            self.default_factory,
            self.init,
            self.repr,
            self.hash,
            self.compare,
            self.serialize,
            self.fserialize,
            self.fdeserialize,
            self.kw_only,
        )
        newinst.name = self.name
        newinst.type = self.type

    __class_getitem__ = classmethod(GenericAlias)


def field(  # noqa: PLR0913 # pylint: disable=R0913, R0917
    *,
    default=MISSING,
    factory=MISSING,
    init=True,
    repr=True,
    hash=None,
    compare=True,
    serialize=True,
    serializer=None,
    deserializer=None,
    kw_only=MISSING,
):
    if default is not MISSING and factory is not MISSING:
        raise ValueError("cannot specify both default and default_factory")
    return Field(default, factory, init, repr, hash, compare, serialize, serializer, deserializer, kw_only)


_SET_TO_SETTER = object()


class Property(Generic[_T], Field):
    def __init__(  # noqa: PLR0913 # pylint: disable=R0913, R0914, R0917
        self,
        fget: Optional[Callable[[Any], _T]] = None,
        fset: Optional[Callable[[Any, Any], None]] = None,
        fdel: Optional[Callable[[Any], None]] = None,
        fvalid: Optional[Callable[[Any, Any], _T]] = None,
        finit: Optional[Callable[[Any, Any], None]] = None,
        *,
        private: Optional[Union[str, Literal[True]]] = None,
        readonly: bool = False,
        notify: Optional[pyqtSignal] = None,
        doc: Optional[str] = None,
        default: Any = MISSING,
        factory: Union[Callable[[], Any], Callable[[Any], Any]] = MISSING,
        init: bool = True,
        repr: bool = True,
        hash: bool = None,
        compare: bool = True,
        serialize: bool = True,
        serializer: Union[SimpleSerializeFunction[_T], SerializerFunction[_T]] = None,
        deserializer: Union[SimpleDeserializeFunction[_T], DeserializerFunction[_T]] = None,
        kw_only: bool = MISSING,
    ):
        super().__init__(default, factory, init, repr, hash, compare, serialize, serializer, deserializer, kw_only)

        if readonly and (fset or fdel):
            raise AttributeError("readonly cannot be True when a setter and/or deleter is provided")

        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.finit = finit

        if private:
            self.private = private
            if fget is None:
                self.fget = self.get_private
            if finit is None:
                self.finit = self.set_private
            if not readonly:
                if fset is None:
                    self.fset = self.set_private
                if fdel is None:
                    self.fdel = self.del_private
        else:
            self.private = None

        if finit == _SET_TO_SETTER:
            self.finit = None

        self.fvalid = fvalid
        self.notify = notify

        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

        if default is MISSING and factory is MISSING and fget:
            name = fget.__qualname__.rsplit(".", 1)[-1]
            # walk the stack through any derived class __init__ calls
            f = sys._getframe(1)
            while isinstance(f.f_locals.get("self", None), (type(self), _BaseGenericAlias)) and f.f_back:
                f = f.f_back
            if f.f_code.co_name == "rds_property" and f.f_back:
                f = f.f_back
            if name in f.f_locals and not isinstance(f.f_locals[name], Field):
                self.default = f.f_locals[name]

    def __call__(self, fget: Callable[[Any], _T]) -> Self:
        return self.getter(fget)

    def __copy__(self):
        newinst = type(self)(
            self.fget,
            self.fset,
            self.fdel,
            self.fvalid,
            self.finit,
            private=self.private,
            notify=self.notify,
            doc=self.__doc__,
            default=self.default,
            factory=self.default_factory,
            init=self.init,
            repr=self.repr,
            hash=self.hash,
            compare=self.compare,
            serialize=self.serialize,
            serializer=self.fserialize,
            deserializer=self.fdeserialize,
            kw_only=self.kw_only,
        )
        newinst.name = self.name
        newinst.type = self.type
        newinst._rebind(newinst, oldself=self)
        return newinst

    def __set_name__(self, owner, name: str):
        self.name = name
        if self.private is True:
            self.private = f"_{name}"

        t = get_type_hints(owner, include_extras=True).get(name, Any)
        if t is Any and self.fget:
            self.type = get_type_hints(self.fget).get("return", Any)
        elif isinstance(t, (_GenericAlias, GenericAlias)):
            orig_t = get_origin(t)

            if orig_t is Annotated:
                args = get_args(t)
                orig_t = args[0]
                if self.fvalid is None and callable(args[1]):
                    self.fvalid = args[1]
            elif orig_t is Union:
                orig_t = get_args(t)

            self.type = orig_t

            if isinstance(orig_t, type) and issubclass(orig_t, MutableSequence) and self.fset == self.set_private:  # pylint: disable=comparison-with-callable
                self.fset = self.set_list
        else:
            self.type = t

    def __get__(self, instance: Any, owner: Optional[type] = None) -> _T:
        if instance is None:
            return self

        if self.fget is None:
            raise AttributeError(f"property {self.name!r} of {owner.__name__!r} object has no getter")

        return self.fget(instance)

    def __set__(self, instance: Any, value: Any):
        if self.fset is None:
            raise AttributeError(f"property {self.name!r} of {type(instance).__name__!r} object has no setter")

        value = self.validate(instance, value)

        if self.notify:
            if self.fget is not None:
                old = self.fget(instance)
                if isinstance(value, Iterable):
                    old = copy(old)
            else:
                old = MISSING  # write-only props still emit a change signal when set

        self.fset(instance, value)

        if self.notify:
            if old is MISSING or old != value:
                boundSignal = self.notify.__get__(instance, type(instance))
                boundSignal.emit()

    def __delete__(self, instance: Any):
        if self.fdel is None:
            raise AttributeError(f"property {self.name!r} of {type(instance).__name__!r} object has no deleter")

        self.fdel(instance)

    def initialize(self, instance: Any, value: _T):
        if self.finit is None and self.fset is None:
            raise AttributeError(f"property {self.name!r} of {type(instance).__name__!r} object has no initializer")

        if value is MISSING:
            if self.default_factory is not MISSING:
                p = list(get_type_hints(self.default_factory).values())
                if len(p) > 1 and isinstance(p[0], type) and issubclass(type(instance), p[0]):
                    value = self.default_factory(instance)
                else:
                    value = self.default_factory()
            elif self.default is not MISSING:
                value = self.default
            else:
                raise ValueError(f"no initial value for property {self.name!r} of {type(instance).__name__!r} object")

        value = self.validate(instance, value)

        if self.finit is not None:
            self.finit(instance, value)
        else:
            self.fset(instance, value)

    def validate(self, instance: Any, value: _T):
        if self.fvalid:
            value = self.fvalid(instance, value)

        try:
            value = coerce_type(self.type, value, self.default)
        except TypeError as e:
            raise TypeError(
                f"{instance.__class__.__name__} property {self.name} "
                f"must be of type {self.type}, but value is {value!r}"
            ) from e

        return value

    def get_private(self, instance):
        return getattr(instance, self.private)

    def set_private(self, instance, value: _T):
        setattr(instance, self.private, value)

    def set_list(self, instance, value: Iterable):
        l: MutableSequence = getattr(instance, self.name, MISSING)
        if l is MISSING:
            raise AttributeError()

        l.clear()
        l.extend(value)

    def del_private(self, instance):
        delattr(instance, self.private)

    def _rebind(self, new_inst: "Property", oldself=None):
        """Rebind property accessors to the new instance if bound to the old instance"""
        if oldself is None:
            oldself = self

        # pylint: disable=unnecessary-dunder-call
        if hasattr(new_inst.fget, "__self__") and new_inst.fget.__self__ is oldself:
            new_inst.fget = new_inst.fget.__func__.__get__(new_inst)
        if hasattr(new_inst.fset, "__self__") and new_inst.fset.__self__ is oldself:
            new_inst.fset = new_inst.fset.__func__.__get__(new_inst)
        if hasattr(new_inst.fdel, "__self__") and new_inst.fdel.__self__ is oldself:
            new_inst.fdel = new_inst.fdel.__func__.__get__(new_inst)
        if hasattr(new_inst.fvalid, "__self__") and new_inst.fvalid.__self__ is oldself:
            new_inst.fvalid = new_inst.fvalid.__func__.__get__(new_inst)
        if hasattr(new_inst.finit, "__self__") and new_inst.finit.__self__ is oldself:
            new_inst.finit = new_inst.finit.__func__.__get__(new_inst)
        if hasattr(new_inst.default_factory, "__self__") and new_inst.default_factory.__self__ is oldself:
            new_inst.default_factory = new_inst.default_factory.__func__.__get__(new_inst)
        if hasattr(new_inst.fserialize, "__self__") and new_inst.fserialize.__self__ is oldself:
            new_inst.fserialize = new_inst.fserialize.__func__.__get__(new_inst)
        if hasattr(new_inst.fdeserialize, "__self__") and new_inst.fdeserialize.__self__ is oldself:
            new_inst.fdeserialize = new_inst.fdeserialize.__func__.__get__(new_inst)
        return new_inst

    def getter(self, fget: Callable[[Any], _T]) -> Self:
        return self._rebind(
            type(self)(
                fget,
                self.fset,
                self.fdel,
                self.fvalid,
                self.finit,
                private=self.private,
                notify=self.notify,
                doc=self.__doc__,
                default=self.default,
                factory=self.default_factory,
                init=self.init,
                repr=self.repr,
                hash=self.hash,
                compare=self.compare,
                serialize=self.serialize,
                serializer=self.fserialize,
                deserializer=self.fdeserialize,
                kw_only=self.kw_only,
            )
        )

    @overload
    def setter(self, fset: Callable[[Any, _T], None]) -> Self: ...

    @overload
    def setter(self, *, set_initializer: bool) -> Callable[[Callable[[Any, _T], None]], Self]: ...

    def setter(
        self, fset: Union[Callable[[Any, _T], None], bool] = None, *, set_initializer: bool = False
    ) -> Union[Self, Callable[[Callable[[Any, _T], None]], Self]]:
        if set_initializer:
            self.finit = _SET_TO_SETTER
            return self.setter

        if fset is None:
            raise TypeError("Setter must be specified")

        return self._rebind(
            type(self)(
                self.fget,
                fset,
                self.fdel,
                self.fvalid,
                self.finit,
                private=self.private,
                notify=self.notify,
                doc=self.__doc__,
                default=self.default,
                factory=self.default_factory,
                init=self.init,
                repr=self.repr,
                hash=self.hash,
                compare=self.compare,
                serialize=self.serialize,
                serializer=self.fserialize,
                deserializer=self.fdeserialize,
                kw_only=self.kw_only,
            )
        )

    def deleter(self, fdel: Callable[[Any], None]) -> Self:
        return self._rebind(
            type(self)(
                self.fget,
                self.fset,
                fdel,
                self.fvalid,
                self.finit,
                private=self.private,
                notify=self.notify,
                doc=self.__doc__,
                default=self.default,
                factory=self.default_factory,
                init=self.init,
                repr=self.repr,
                hash=self.hash,
                compare=self.compare,
                serialize=self.serialize,
                serializer=self.fserialize,
                deserializer=self.fdeserialize,
                kw_only=self.kw_only,
            )
        )

    def validator(self, fvalid: Callable[[Any, Any], _T]) -> Self:
        return self._rebind(
            type(self)(
                self.fget,
                self.fset,
                self.fdel,
                fvalid,
                self.finit,
                private=self.private,
                notify=self.notify,
                doc=self.__doc__,
                default=self.default,
                factory=self.default_factory,
                init=self.init,
                repr=self.repr,
                hash=self.hash,
                compare=self.compare,
                serialize=self.serialize,
                serializer=self.fserialize,
                deserializer=self.fdeserialize,
                kw_only=self.kw_only,
            )
        )

    def initializer(self, finit: Callable[[Any, _T], None]) -> Self:
        return self._rebind(
            type(self)(
                self.fget,
                self.fset,
                self.fdel,
                self.fvalid,
                finit,
                private=self.private,
                notify=self.notify,
                doc=self.__doc__,
                default=self.default,
                factory=self.default_factory,
                init=self.init,
                repr=self.repr,
                hash=self.hash,
                compare=self.compare,
                serialize=self.serialize,
                serializer=self.fserialize,
                deserializer=self.fdeserialize,
                kw_only=self.kw_only,
            )
        )

    def serializer(self, fserializer: Callable[[Any, _T], None]) -> Self:
        return self._rebind(
            type(self)(
                self.fget,
                self.fset,
                self.fdel,
                self.fvalid,
                self.finit,
                private=self.private,
                notify=self.notify,
                doc=self.__doc__,
                default=self.default,
                factory=self.default_factory,
                init=self.init,
                repr=self.repr,
                hash=self.hash,
                compare=self.compare,
                serialize=self.serialize,
                serializer=fserializer,
                deserializer=self.fdeserialize,
                kw_only=self.kw_only,
            )
        )

    def deserializer(self, fdeserializer: Callable[[Any, _T], None]) -> Self:
        return self._rebind(
            type(self)(
                self.fget,
                self.fset,
                self.fdel,
                self.fvalid,
                self.finit,
                private=self.private,
                notify=self.notify,
                doc=self.__doc__,
                default=self.default,
                factory=self.default_factory,
                init=self.init,
                repr=self.repr,
                hash=self.hash,
                compare=self.compare,
                serialize=self.serialize,
                serializer=self.fserialize,
                deserializer=fdeserializer,
                kw_only=self.kw_only,
            )
        )

    @overload
    def factory(self, factory: Callable[[Any], _T]) -> Self: ...

    @overload
    def factory(self, *, override) -> Self: ...

    @overload
    def factory(self, factory: Callable[[Any], _T], *, override) -> Self: ...

    def factory(self, factory: Callable[[Any], _T] = None, *, override=False) -> Self:
        if not override and self.default is not MISSING:
            raise TypeError("Cannot set both factory and default")

        if override and factory is None and self.default is not MISSING:
            # need to create a new instance so we don't trample the default value of the super class
            return self._rebind(
                type(self)(
                    self.fget,
                    self.fset,
                    self.fdel,
                    self.fvalid,
                    self.finit,
                    private=self.private,
                    notify=self.notify,
                    doc=self.__doc__,
                    default=MISSING,
                    factory=factory,
                    init=self.init,
                    repr=self.repr,
                    hash=self.hash,
                    compare=self.compare,
                    serialize=self.serialize,
                    serializer=self.fserialize,
                    deserializer=self.fdeserialize,
                    kw_only=self.kw_only,
                )
            ).factory

        if not isinstance(factory, (Factory, staticmethod, classmethod)):
            factory = Factory(factory)

        return self._rebind(
            type(self)(
                self.fget,
                self.fset,
                self.fdel,
                self.fvalid,
                self.finit,
                private=self.private,
                notify=self.notify,
                doc=self.__doc__,
                default=self.default,
                factory=factory,
                init=self.init,
                repr=self.repr,
                hash=self.hash,
                compare=self.compare,
                serialize=self.serialize,
                serializer=self.fserialize,
                deserializer=self.fdeserialize,
                kw_only=self.kw_only,
            )
        )


def rds_property(  # noqa: PLR0913 # pylint: disable=R0913, R0914, R0917
    fget: Optional[Callable[[Any], _T]] = None,
    fset: Union[bool, Callable[[Any, Any], None]] = None,
    fdel: Optional[Callable[[Any], None]] = None,
    fvalid: Optional[Callable[[Any, Any], _T]] = None,
    finit: Optional[Callable[[Any, Any], None]] = None,
    *,
    private=None,
    readonly=False,
    notify=None,
    doc=None,
    default: Union[_T, _MISSING_TYPE] = MISSING,
    factory: Union[Callable[[Any], _T], Callable[[], _T], _MISSING_TYPE] = MISSING,
    init=True,
    repr=True,
    hash=None,
    compare=True,
    serialize=True,
    serializer=None,
    deserializer=None,
    kw_only=MISSING,
) -> Property[_T]:
    if default is not MISSING and factory is not MISSING:
        raise ValueError("cannot specify both default and default_factory")
    return Property[_T](
        fget,
        fset,
        fdel,
        fvalid,
        finit,
        private=private,
        readonly=readonly,
        notify=notify,
        doc=doc,
        default=default,
        factory=factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        serialize=serialize,
        serializer=serializer,
        deserializer=deserializer,
        kw_only=kw_only,
    )
