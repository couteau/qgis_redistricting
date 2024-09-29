import math
import numbers
import sys
from copy import copy
from types import GenericAlias
from typing import (  # pylint: disable=no-name-in-module
    Annotated,
    Any,
    Callable,
    Generic,
    Literal,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Self,
    Sequence,
    TypeVar,
    Union,
    _GenericAlias,
    _UnionGenericAlias,
    get_args,
    get_origin,
    get_type_hints
)

from qgis.PyQt.QtCore import pyqtSignal


class _MISSING_TYPE:
    def __bool__(self):
        return False


MISSING = _MISSING_TYPE()


def get_real_type(t: type):
    v = None
    if isinstance(t, (_GenericAlias, GenericAlias)) and not isinstance(t, _UnionGenericAlias):
        args = get_args(t)
        t = get_origin(t)
        if t is Annotated:
            t = args[0]
            v = args[1]
        elif t is Literal:
            t = type(args[0])

    return t, v


def type_name(t: type):
    if isinstance(t, _GenericAlias):
        if isinstance(t, _UnionGenericAlias):
            if t.__name__ == "Optional":
                return f'{get_args(t)[0].__name__} or None'
            return ' or '.join(a.__name__ for a in get_args(t))
        t = get_origin(t)

    return repr(t.__name__)


def not_empty(instance=None, value=None):
    if instance is None and value is None:
        return not_empty

    if not isinstance(value, str) or value != "":
        return value

    raise ValueError("Value must not be empty")


class in_range:
    def __init__(self, minValue=math.inf, maxValue=math.inf):
        self.min = minValue
        self.max = maxValue

    def __call__(self, instance, value):
        if self.min.__eq__(value) is NotImplemented:
            raise TypeError("Range and value are incompatible types")

        if not self.min <= value <= self.max:
            raise ValueError(f"Value must be between {self.min} and {self.max}")

        return value


_T = TypeVar("_T")


class Factory(Generic[_T]):
    """Factory class for wrapping default factory functions that take the instance as a parameter
    """

    def __init__(self, factory: Callable[[Any], _T], with_owner: bool = True, defer: bool = False):
        """Constructor for Factory class for initializing model attributes

        Args:
            factory (Callable): The factory function wrapped by this Factory instance.
            with_owner (bool, optional): Whether the factory function takes the instance as an argument. Defaults to True.
            defer (bool, optional): Whether the factory should be called after all other instance attributes have been set. Defaults to False.
        """
        self.factory = factory
        self.with_owner = with_owner
        self.defer = defer

    def __call__(self, owner) -> _T:
        if self.with_owner:
            return self.factory(owner)

        return self.factory()


ListFactory = Factory(list, False)
DictFactory = Factory(dict, False)


class rds_property(Generic[_T]):
    def set_list(self: 'rds_property', instance: Any, value: _T):
        v: Union[MutableSequence, MutableMapping] = self.__get__(instance)  # pylint: disable=unnecessary-dunder-call
        if v is not MISSING:
            v.clear()
            if isinstance(v, MutableSequence):
                v.extend(value)
            else:
                v.update(value)
        else:
            setattr(instance, self.private, value)

    def set_private(self: 'rds_property', instance: Any, value: _T):
        setattr(instance, self.private, value)

    def __init__(
        self,
        fget: Optional[Callable[[Any], _T]] = None,
        fset: Optional[Callable[[Any, _T], None]] = None,
        fdel: Optional[Callable[[Any], None]] = None,
        doc: Optional[str] = None,
        private: Union[str, Literal[True], None] = None,
        readonly: bool = False,
        fvalid: Optional[Callable[[Any, Any], _T]] = None,
        notify: Optional[pyqtSignal] = None,
        default: Union[_T, _MISSING_TYPE] = MISSING,
        factory: Callable[[Any], _T] = MISSING,
        strict: bool = False,
        init: bool = True,
        serialize: Union[bool, Callable[[_T, dict], Any]] = True
    ):
        self.fget = fget

        if fset is rds_property.set_list or (hasattr(fset, "__func__") and fset.__func__ is rds_property.set_list):
            self.fset = self.set_list
        elif (fset is None and private is not None) or (hasattr(fset, "__func__") and fset.__func__ is rds_property.set_private):
            self.fset = self.set_private
        else:
            self.fset = fset

        self.fdel = fdel
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

        self.name = None
        self.type = Any
        self.private = private
        self.readonly = readonly
        self.fvalid = fvalid
        self.notify = notify
        self.default = default
        self.default_factory = factory
        self.strict = strict
        self.init = init
        self.serialize = serialize

        if default is MISSING and factory is MISSING and fget:
            name = fget.__qualname__.rsplit(".", 1)[-1]
            # walk the stack through any derived class __init__ calls
            f = sys._getframe(1)
            while isinstance(f.f_locals.get("self", None), type(self)) and f.f_back:
                f = f.f_back
            if name in f.f_locals and not isinstance(f.f_locals[name], type(self)):
                self.default = f.f_locals[name]

    def __call__(self, fget: Callable[[Any], _T]) -> Self:
        return type(self)(fget, self.fset, self. fdel, self.__doc__,
                          self.private, self.readonly, self.fvalid, self.notify,
                          self.default, self.default_factory,
                          self.strict, self.init, self.serialize)

    def __get__(self, instance: Any, owner: Optional[type] = None) -> _T:
        if instance is None:
            return self

        if self.private and not hasattr(instance, self.private):
            return MISSING

        if not self.fget and self.private:
            return getattr(instance, self.private)

        if self.fget is None:
            raise AttributeError(f'property {self.name!r} of {owner.__name__!r} object has no getter')

        return self.fget(instance)

    def __set__(self, instance: Any, value: _T):
        init = (self.private and not hasattr(instance, self.private)) \
            or getattr(instance, self.name, MISSING) is MISSING

        if self.readonly and not init:
            raise AttributeError(f'{instance.__class__.__name__}.{self.name} is readonly')

        if self.fset is None:
            raise AttributeError(f'property {self.name!r} of {instance.__class__.__name__!r} object has no setter')

        if self.notify and not init:
            oldValue = copy(self.__get__(instance))

        self.fset(instance, self.validate(instance, value))

        if self.notify and not init:
            newValue = self.__get__(instance)
            if oldValue != newValue:
                signal = self.notify.__get__(instance, type(instance))
                signal.emit()

    def __delete__(self, instance: Any):
        if self.fdel is None:
            raise AttributeError(f'property {self.name!r} of {instance.__class__.__name__!r} object has no deleter')

        self.fdel(instance)

    def __set_name__(self, owner, name: str):
        self.name = name

        if self.private is True:
            self.private = f"_{name}"

        t = get_type_hints(owner, include_extras=True).get(name, Any)
        self.type, valid = get_real_type(t)

        if valid is not None and self.fvalid is None:
            self.fvalid = valid

    def _check_type(self, instance, value):
        if self.type is Any:
            return value

        if isinstance(self.type, type):
            # numeric value is valid for int if it can be cast to int without loss of precision
            if issubclass(self.type, int) and isinstance(value, numbers.Real) and self.type(value) == value:
                return self.type(value)

            # any real number can be validly assigned to float
            if issubclass(self.type, float) and isinstance(value, numbers.Real):
                return self.type(value)

            if issubclass(self.type, MutableSequence) and isinstance(value, Sequence):
                return value

            if issubclass(self.type, MutableMapping) and isinstance(value, Mapping):
                return value

        if isinstance(self.type, _UnionGenericAlias) and isinstance(value, get_args(self.type)):
            return value

        if isinstance(value, self.type):
            return value

        raise TypeError(
            f'Cannot set {instance.__class__.__name__}.{self.name} to {value!r}: value must be of type {type_name(self.type)}'
        )

    def validate(self, instance, value) -> _T:
        if not self.strict and value is None:
            return value

        if self.fvalid:
            value = self.fvalid(instance, value)

        return self._check_type(instance, value)

    def getter(self, fget: Callable[[Any], _T]) -> Self:
        return type(self)(fget, self.fset, self.fdel, self.__doc__,
                          self.private, self.readonly, self.fvalid, self.notify,
                          self.default, self.default_factory,
                          self.strict, self.init, self.serialize)

    def setter(self, fset: Callable[[Any, _T], None]) -> Self:
        return type(self)(self.fget, fset, self.fdel, self.__doc__,
                          self.private, self.readonly, self.fvalid, self.notify,
                          self.default, self.default_factory,
                          self.strict, self.init, self.serialize)

    def deleter(self, fdel: Callable[[Any], None]) -> Self:
        return type(self)(self.fget, self.fset, fdel, self.__doc__,
                          self.private, self.readonly, self.fvalid, self.notify,
                          self.default, self.default_factory,
                          self.strict, self.init, self.serialize)

    def validator(self, fvalid: Callable[[Any, Any], _T]) -> Self:
        return type(self)(self.fget, self.fset, self.fdel, self.__doc__,
                          self.private, self.readonly, fvalid, self.notify,
                          self.default, self.default_factory,
                          self.strict, self.init, self.serialize)

    def factory(self, factory: Callable[[Any], _T]) -> Self:
        if self.default is not MISSING:
            raise TypeError("Cannot set both factory and default")
        return type(self)(self.fget, self.fset, self.fdel, self.__doc__,
                          self.private, self.readonly, self.fvalid, self.notify,
                          self.default, factory, self.strict, self.init, self.serialize)
