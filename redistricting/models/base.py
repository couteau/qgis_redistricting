# -*- coding: utf-8 -*-
"""Base model

        begin                : 2024-06-05
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
from functools import wraps
from typing import (
    Any,
    Callable,
    Generic,
    Optional,
    TypeVar,
    TypeVarTuple,
    dataclass_transform,
    get_type_hints
)

from qgis.PyQt.QtCore import QObject

from .prop import (
    MISSING,
    rds_property
)

F = TypeVar("F")


class Factory(Generic[F]):
    """Factory class for wrapping default factory functions that take the instance as a parameter
    """

    def __init__(self, factory: Callable[[Any], F], with_owner: bool = True, defer: bool = False):
        """Constructor for Factory class for initializing model attributes

        Args:
            factory (Callable): The factory function wrapped by this Factory instance.
            with_owner (bool, optional): Whether the factory function takes the instance as an argument. Defaults to True.
            defer (bool, optional): Whether the factory should be called after all other instance attributes have been set. Defaults to False.
        """
        self.factory = factory
        self.with_owner = with_owner
        self.defer = defer

    def __call__(self, owner) -> F:
        if self.with_owner:
            return self.factory(owner)

        return self.factory()


ListFactory = Factory(list, False)
DictFactory = Factory(dict, False)

T = TypeVar("T")
C = TypeVarTuple("C")
_FACTORY_MARKER = object()


@dataclass_transform(field_specifiers=(rds_property, property, Factory))
class RdsBaseModel(QObject):
    @classmethod
    def has_post_init(cls):
        if cls.__dict__.get("__post_init__", None):
            return True

        for b in cls.__mro__:
            if b is not RdsBaseModel and b.__dict__.get("__post_init__", None):
                return True

        return False

    @classmethod
    def make_init_signature(cls) -> inspect.Signature:
        args = []
        for a, t in get_type_hints(cls, include_extras=True).items():
            if a == "parent":
                continue
            init = True
            default = getattr(cls, a, inspect.Parameter.empty)
            if isinstance(default, rds_property):
                init = default.init
                if default.default_factory is not MISSING:
                    default = _FACTORY_MARKER
                elif default.default is not MISSING:
                    default = default.default
                else:
                    default = inspect.Parameter.empty
            elif isinstance(default, Factory):
                default = _FACTORY_MARKER
            elif isinstance(default, property):
                default = inspect.Parameter.empty

            if init:
                args.append(inspect.Parameter(
                    a,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=default,
                    annotation=t
                ))

        args.append(
            inspect.Parameter(
                'parent',
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=Optional[QObject]
            )
        )

        if cls.has_post_init():
            args.append(inspect.Parameter('extra', inspect.Parameter.VAR_KEYWORD))

        return inspect.Signature(args, return_annotation=None)

    def __init_subclass__(cls):
        def wrap_init(init_func):
            @wraps(init_func)
            def wrapped_init(self, *args, **kwargs):
                init_func(self, *args, **kwargs)

            wrapped_init.__signature__ = cls.make_init_signature()
            return wrapped_init

        super().__init_subclass__()
        setattr(cls, "__init__", wrap_init(RdsBaseModel.__init__))

    def __pre_init__(self):
        ...

    def __post_init__(self, **kwargs):  # pylint: disable=unused-argument
        ...

    def __init__(self, *args, **kwargs):
        sig = inspect.signature(type(self).__init__)
        bound_args = sig.bind(*args, **kwargs)
        parent = bound_args.arguments.pop("parent", None)
        extra = bound_args.arguments.pop("extra", {})

        super().__init__(parent)

        self.__pre_init__()

        deferred = {}
        for a in get_type_hints(type(self)):
            if a == "parent":
                continue

            if a in sig.parameters:
                p = sig.parameters[a]
                if a in bound_args.arguments:
                    setattr(self, a, bound_args.arguments[a])
                    continue
                elif p.default == _FACTORY_MARKER:
                    factory = getattr(type(self), a)
                    if isinstance(factory, rds_property):
                        factory = factory.default_factory
                    default = MISSING
                else:
                    default = p.default
                    factory = MISSING
            else:
                default = getattr(type(self), a)
                if isinstance(default, Factory):
                    factory = default
                    default = MISSING
                elif isinstance(default, rds_property):
                    factory = default.default_factory
                    default = default.default
                else:
                    factory = MISSING

            if isinstance(factory, Factory):
                if factory.defer:
                    deferred[a] = factory
                else:
                    setattr(self, a, factory(self))
            elif factory is not MISSING:
                setattr(self, a, factory())
            elif default is not inspect.Parameter.empty and default is not MISSING:
                setattr(self, a, default)

        for a, factory in deferred.items():
            setattr(self, a, factory(self))

        self.__post_init__(**extra)

    def __repr__(self):
        cls_name = type(self).__name__
        d = {f: getattr(self, f) for f in get_type_hints(type(self))}
        return f"{cls_name}({', '.join(f'{f}={v!r}' for f, v in d.items())})"