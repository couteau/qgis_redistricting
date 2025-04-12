# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - dataclass-like model and property classes

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
import functools
import inspect
import math
import numbers
import sys
from copy import copy
from enum import Enum
from reprlib import recursive_repr
from types import GenericAlias
from typing import (  # pylint: disable=no-name-in-module
    Annotated,
    Any,
    Callable,
    ClassVar,
    Generic,
    Iterable,
    Literal,
    MutableSequence,
    Optional,
    Self,
    Type,
    TypeVar,
    Union,
    _AnnotatedAlias,
    _BaseGenericAlias,
    _GenericAlias,
    _strip_annotations,
    _UnionGenericAlias,
    dataclass_transform,
    get_args,
    get_origin,
    get_type_hints,
    overload
)

from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from .serialization import (
    _memo,
    deserialize_value,
    kebab_dict,
    kebab_to_camel,
    register_serializer,
    serialize_value
)

# pylint: disable=redefined-builtin


class _MISSING_TYPE:
    def __bool__(self):
        return False


MISSING = _MISSING_TYPE()


def _is_classvar(a_type):
    # Borrowed from `dataclasses` module
    return (a_type is ClassVar
            or (type(a_type) is _GenericAlias
                and a_type.__origin__ is ClassVar))


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
                return f'{get_args(t)[0].__name__} or None'
            return ' or '.join(a.__name__ for a in get_args(t))

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
    """Factory class for wrapping default factory functions that take the instance as a parameter
    """

    def __init__(
        self,
        factory: Union[Callable[[], _T], Callable[[Any], _T]],
        with_owner: bool = True,
        defer: bool = False
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
    __slots__ = ('type', )

    def __init__(self, t):
        self.type = t

    def __repr__(self):
        if isinstance(self.type, type):
            tname = self.type.__name__
        else:
            tname = repr(self.type)
        return f'InitVar[{tname}]'

    def __class_getitem__(cls, t):
        return InitVar(t)


class PrivateVar:
    __slots__ = ('type', )

    def __init__(self, t):
        self.type = t

    def __repr__(self):
        if isinstance(self.type, type):
            tname = self.type.__name__
        else:
            tname = repr(self.type)
        return f'PrivateVar[{tname}]'

    def __class_getitem__(cls, t):
        return PrivateVar(t)


class FieldType(Enum):
    FIELD = 0
    INIT_VAR = 1
    CLASS_VAR = 2


class Field:

    def __init__(
            self,
            default: Any = MISSING,
            factory: Union[Callable[[], Any], Callable[[Any], Any]] = MISSING,
            init: bool = True,
            repr: bool = True,
            hash: bool = None,
            compare: bool = True,
            serialize: bool = True,
            kw_only: bool = MISSING
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
        self.kw_only = kw_only
        self._field_type = FieldType.FIELD

    def __set_name__(self, owner, name: str):
        self.name = name
        self.type = get_type_hints(owner).get(name, Any)

    @recursive_repr()
    def __repr__(self):
        return (f'{self.__class__.__name__}('
                f'name={self.name!r},'
                f'type={self.type!r},'
                f'default={self.default!r},'
                f'default_factory={self.default_factory!r},'
                f'init={self.init!r},'
                f'repr={self.repr!r},'
                f'hash={self.hash!r},'
                f'compare={self.compare!r},'
                f'serialize={self.serialize},'
                f'kw_only={self.kw_only!r}'
                ')')

    __class_getitem__ = classmethod(GenericAlias)


def field(*, default=MISSING, factory=MISSING, init=True,
          repr=True, hash=None, compare=True, serialize=True, kw_only=MISSING):
    if default is not MISSING and factory is not MISSING:
        raise ValueError('cannot specify both default and default_factory')
    return Field(default, factory, init, repr, hash, compare, serialize, kw_only)


class _accessor:
    def __init__(self, faccessor):
        self.faccessor = faccessor

    def __get__(self, instance, owner):
        if instance is None:
            return self

        return self.faccessor.__get__(instance)


def make_accessor(fn):
    return _accessor(fn)


@make_accessor
def set_list(prop: 'Property', instance, value: Iterable):
    l: MutableSequence = getattr(instance, prop.name, MISSING)
    if l is MISSING:
        raise AttributeError()

    l.clear()
    l.extend(value)


_SET_TO_SETTER = object()


class Property(Generic[_T], Field):
    def __init__(
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
        kw_only: bool = MISSING
    ):
        super().__init__(default, factory, init, repr, hash, compare, serialize, kw_only)

        if readonly and (fset or fdel):
            raise AttributeError("readonly cannot be True when a setter and/or deleter is provided")

        self.fget = fget.__get__(self, self.__class__) if isinstance(fget, _accessor) else fget
        self.fset = fset.__get__(self, self.__class__) if isinstance(fset, _accessor) else fset
        self.fdel = fdel.__get__(self, self.__class__) if isinstance(fdel, _accessor) else fdel
        self.finit = finit.__get__(self, self.__class__) if isinstance(finit, _accessor) else finit

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

        self.fvalid = fvalid.__get__(self, self.__class__) if isinstance(fvalid, _accessor) else fvalid
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

    def __set_name__(self, owner, name: str):
        self.name = name
        if self.private is True:
            self.private = f"_{name}"

        t = get_type_hints(owner, include_extras=True).get(name, Any)
        if t is Any and self.fget:
            self.type = get_type_hints(self.fget).get('return', Any)
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
            raise AttributeError(f'property {self.name!r} of {owner.__name__!r} object has no getter')

        return self.fget(instance)

    def __set__(self, instance: Any, value: Any):
        if self.fset is None:
            raise AttributeError(f'property {self.name!r} of {type(instance).__name__!r} object has no setter')

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
            raise AttributeError(f'property {self.name!r} of {type(instance).__name__!r} object has no deleter')

        self.fdel(instance)

    def initialize(self, instance: Any, value: _T):
        if self.finit is None and self.fset is None:
            raise AttributeError(f'property {self.name!r} of {type(instance).__name__!r} object has no initializer')

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

    def rebind(self, new_inst: 'Property'):
        """Rebind property accessors to the new instance if bound to the old instance"""
        # pylint: disable=unnecessary-dunder-call
        if hasattr(new_inst.fget, "__self__") and new_inst.fget.__self__ is self:
            new_inst.fget = new_inst.fget.__func__.__get__(new_inst)
        if hasattr(new_inst.fset, "__self__") and new_inst.fset.__self__ is self:
            new_inst.fset = new_inst.fset.__func__.__get__(new_inst)
        if hasattr(new_inst.fdel, "__self__") and new_inst.fdel.__self__ is self:
            new_inst.fdel = new_inst.fdel.__func__.__get__(new_inst)
        if hasattr(new_inst.fvalid, "__self__") and new_inst.fvalid.__self__ is self:
            new_inst.fvalid = new_inst.fvalid.__func__.__get__(new_inst)
        if hasattr(new_inst.finit, "__self__") and new_inst.finit.__self__ is self:
            new_inst.finit = new_inst.finit.__func__.__get__(new_inst)
        if hasattr(new_inst.default_factory, "__self__") and new_inst.default_factory.__self__ is self:
            new_inst.default_factory = new_inst.default_factory.__func__.__get__(new_inst)
        return new_inst

    def getter(self, fget: Callable[[Any], _T]) -> Self:
        return self.rebind(type(self)(fget, self.fset, self.fdel, self.fvalid, self.finit,
                                      private=self.private, notify=self.notify, doc=self.__doc__,
                                      default=self.default, factory=self.default_factory,
                                      init=self.init, repr=self.repr, hash=self.hash, compare=self.compare,
                                      serialize=self.serialize, kw_only=self.kw_only))

    @overload
    def setter(self, fset: Callable[[Any, _T], None]) -> Self:
        ...

    @overload
    def setter(self, *, set_initializer: bool) -> Callable[[Callable[[Any, _T], None]], Self]:
        ...

    def setter(
        self, fset: Union[Callable[[Any, _T], None], bool] = None, *, set_initializer: bool = False
    ) -> Union[Self, Callable[[Callable[[Any, _T], None]], Self]]:
        if set_initializer:
            self.finit = _SET_TO_SETTER
            return self.setter

        if fset is None:
            raise TypeError("Setter must be specified")

        return self.rebind(type(self)(self.fget, fset, self.fdel, self.fvalid, self.finit,
                                      private=self.private, notify=self.notify, doc=self.__doc__,
                                      default=self.default, factory=self.default_factory,
                                      init=self.init, repr=self.repr, hash=self.hash, compare=self.compare,
                                      serialize=self.serialize, kw_only=self.kw_only))

    def deleter(self, fdel: Callable[[Any], None]) -> Self:
        return self.rebind(type(self)(self.fget, self.fset, fdel, self.fvalid, self.finit,
                                      private=self.private, notify=self.notify, doc=self.__doc__,
                                      default=self.default, factory=self.default_factory,
                                      init=self.init, repr=self.repr, hash=self.hash, compare=self.compare,
                                      serialize=self.serialize, kw_only=self.kw_only))

    def validator(self, fvalid: Callable[[Any, Any], _T]) -> Self:
        return self.rebind(type(self)(self.fget, self.fset, self.fdel, fvalid, self.finit,
                                      private=self.private, notify=self.notify, doc=self.__doc__,
                                      default=self.default, factory=self.default_factory,
                                      init=self.init, repr=self.repr, hash=self.hash, compare=self.compare,
                                      serialize=self.serialize, kw_only=self.kw_only))

    def initializer(self, finit: Callable[[Any, _T], None]) -> Self:
        return self.rebind(type(self)(self.fget, self.fset, self.fdel, self.fvalid, finit,
                                      private=self.private, notify=self.notify, doc=self.__doc__,
                                      default=self.default, factory=self.default_factory,
                                      init=self.init, repr=self.repr, hash=self.hash, compare=self.compare,
                                      serialize=self.serialize, kw_only=self.kw_only))

    def factory(self, factory: Callable[[Any], _T]) -> Self:
        if self.default is not MISSING:
            raise TypeError("Cannot set both factory and default")
        if not isinstance(factory, (Factory, staticmethod, classmethod)):
            factory = Factory(factory)
        return self.rebind(type(self)(self.fget, self.fset, self.fdel, self.fvalid, self.finit,
                                      private=self.private, notify=self.notify,
                                      doc=self.__doc__, default=self.default, factory=factory,
                                      init=self.init, repr=self.repr, hash=self.hash, compare=self.compare,
                                      serialize=self.serialize, kw_only=self.kw_only))


def rds_property(fget: Optional[Callable[[Any], _T]] = None,
                 fset: Union[bool, Callable[[Any, Any], None]] = None,
                 fdel: Optional[Callable[[Any], None]] = None,
                 fvalid: Optional[Callable[[Any, Any], _T]] = None,
                 finit: Optional[Callable[[Any, Any], None]] = None,
                 *,
                 private=None, readonly=False,
                 notify=None, doc=None,
                 default: Union[_T, _MISSING_TYPE] = MISSING,
                 factory: Union[Callable[[Any], _T], Callable[[], _T], _MISSING_TYPE] = MISSING,
                 init=True, repr=True, hash=None, compare=True, serialize=True, kw_only=MISSING):
    if default is not MISSING and factory is not MISSING:
        raise ValueError('cannot specify both default and default_factory')
    return Property[_T](fget, fset, fdel, fvalid, finit, private=private, readonly=readonly,
                        notify=notify, doc=doc, default=default, factory=factory, init=init,
                        repr=repr, hash=hash, compare=compare, serialize=serialize, kw_only=kw_only)


class _FACTORY_MARKER_TYPE:
    def __repr__(self):
        return "_FACTORY_MARKER"


_FACTORY_MARKER = _FACTORY_MARKER_TYPE()


def compare_models(self, other):
    if not isinstance(other, self.__class__):
        return NotImplemented

    if len(fields(self)) == 0:
        return False

    for f in fields(self):
        if f.compare:
            if getattr(self, f.name) != getattr(other, f.name):
                return False

    return True


@dataclass_transform(field_specifiers=(rds_property, Property, field, Field))
class RdsBaseModel(QObject):
    __fields__: list[Field]

    @classmethod
    def has_method(cls, method_name):
        if cls.__dict__.get(method_name, None):
            return True

        for b in cls.__mro__:
            if b is not RdsBaseModel and b.__dict__.get(method_name, None):
                return True

        return False

    @classmethod
    def make_init_signature(cls) -> inspect.Signature:
        args = []
        for f in cls.__fields__:
            if f.init and f._field_type != FieldType.CLASS_VAR:  # pylint: disable=protected-access
                if f.default_factory is not MISSING:
                    default = _FACTORY_MARKER
                elif f.default is not MISSING:
                    default = f.default
                else:
                    default = inspect.Parameter.empty

                if f.kw_only:
                    kind = inspect.Parameter.KEYWORD_ONLY
                else:
                    kind = inspect.Parameter.POSITIONAL_OR_KEYWORD

                args.append(inspect.Parameter(f.name, kind, default=default, annotation=f.type))

        args.append(
            inspect.Parameter(
                'parent',
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=Optional[QObject]
            )
        )

        return inspect.Signature(args, return_annotation=None)

    def __init_subclass__(cls):
        def wrap_init(init_func):
            @functools.wraps(init_func)
            def wrapped_init(self, *args, **kwargs):
                init_func(self, *args, **kwargs)

            wrapped_init.__signature__ = cls.make_init_signature()
            return wrapped_init

        super().__init_subclass__()
        flds = {}

        default_seen = False
        kwonly_seen = False
        cls_annotations = get_type_hints(cls, include_extras=True)
        for n, t in cls_annotations.items():
            if n.startswith("__") or isinstance(t, PrivateVar):
                continue

            default = getattr(cls, n, MISSING)
            if isinstance(default, Field):
                fld = default
                if default.default_factory is not MISSING:
                    default = _FACTORY_MARKER
                else:
                    default = default.default
            else:
                fld = Field(kw_only=kwonly_seen or MISSING)
                fld.__set_name__(cls, n)
                if isinstance(default, Factory):
                    fld.default_factory = default
                    default = _FACTORY_MARKER
                elif isinstance(default, property):
                    default = MISSING  # inspect.Parameter.empty
                else:
                    fld.default = default

            if fld.kw_only is MISSING:
                fld.kw_only = cls.__dataclass_transform__['kw_only_default']  # pylint: disable=no-member

            if default_seen and default is MISSING:
                raise SyntaxError('non-default argument follows default argument')
            default_seen = default is not MISSING

            if kwonly_seen and fld.kw_only is False:
                raise SyntaxError('non-keyword argument follows keyword argument')
            kwonly_seen = fld.kw_only

            if isinstance(t, InitVar):
                fld._field_type = FieldType.INIT_VAR
                fld.serialize = False
            elif _is_classvar(t):
                fld._field_type = FieldType.CLASS_VAR
                fld.serialize = False

            flds[n] = fld

        setattr(cls, "__fields__", flds.values())
        setattr(cls, "__init__", wrap_init(getattr(cls, "__init__")))
        if cls.__dataclass_transform__['eq_default']:
            setattr(cls, "__eq__", compare_models)

    def __pre_init__(self):
        ...

    def __post_init__(self, **kwargs):  # pylint: disable=unused-argument
        ...

    def __init__(self, *args, **kwargs):
        sig = inspect.signature(type(self).__init__)

        # remove any passed in missing params
        args = tuple(a for a in args if a is not MISSING)
        kwargs = {k: v for k, v in kwargs.items() if v is not MISSING}

        bound_args = sig.bind(*args, **kwargs)
        parent = bound_args.arguments.pop("parent", None)

        super().__init__(parent)

        self.__pre_init__()

        deferred: list[Field] = []
        post_init_args = {}
        for f in self.__fields__:
            if f.name in sig.parameters:
                p = sig.parameters[f.name]
                if f.name in bound_args.arguments:
                    value = bound_args.arguments[f.name]
                else:
                    if p.default == _FACTORY_MARKER:
                        factory = f.default_factory
                        default = MISSING
                    else:
                        default = f.default
                        factory = MISSING

                    if isinstance(factory, Factory):
                        if factory.defer:
                            deferred.append(f)
                            continue
                        else:
                            value = factory(self)
                    elif factory is not MISSING:
                        value = factory()
                    elif default is not inspect.Parameter.empty and default is not MISSING:
                        value = default
                    else:
                        value = MISSING

                if value is not MISSING:
                    if f._field_type == FieldType.FIELD:
                        if isinstance(f, Property):
                            f.initialize(self, value)
                        else:
                            setattr(self, f.name, value)
                    else:
                        post_init_args[f.name] = value

        for f in deferred:
            value = f.default_factory(self)
            if f._field_type == FieldType.FIELD:
                if isinstance(f, Property):
                    f.initialize(self, value)
                else:
                    setattr(self, f.name, value)
            else:
                post_init_args[f.name] = value

        self.__post_init__(**post_init_args)

    def __deepcopy__(self, memo):
        return deserialize_model(self.__class__, serialize_model(self, memo, False), self.parent())

    @recursive_repr()
    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(f'{f.name}={getattr(self, f.name)!r}' for f in self.__fields__ if f._field_type == FieldType.FIELD and f.repr)})"


def fields(cls: Union[RdsBaseModel, type[RdsBaseModel]]) -> list[Field]:
    if not isinstance(cls, RdsBaseModel) or (isinstance(cls, type) and not issubclass(cls, RdsBaseModel)):
        raise TypeError(f"{cls!r} is not an instance or subclass of RdsBaseModel")

    return [f for f in cls.__fields__ if f._field_type == FieldType.FIELD]  # pylint: disable=protected-access


def serialize_model(obj, memo=None, exclude_none=True):
    """Right now we just ignore already memo objects to avoid recursion.
    TODO: come up with a way to cross-reference
    """

    d = {}
    for prop in fields(obj):
        if not prop.serialize:
            continue

        if callable(prop.serialize):
            value = prop.serialize(value, memo)
        else:
            value = serialize_value(getattr(obj, prop.name), memo)

        if value is not _memo and (value is not None or not exclude_none):
            d[prop.name] = value

    return kebab_dict(d.items())


_ModelType = TypeVar("_ModelType", bound=RdsBaseModel)


def deserialize_model(cls: Type[_ModelType], data: dict[str, Any], parent: Optional[QObject] = None) -> _ModelType:
    kw = {}

    flds = get_type_hints(cls)

    for k, v in data.items():
        f = kebab_to_camel(k)
        if f in flds:
            t = flds[f]
        else:
            continue

        if t is not None:
            v = deserialize_value(t, v)

        kw[f] = v

    return cls(**kw, parent=parent)


register_serializer(RdsBaseModel, serialize_model, deserialize_model)
