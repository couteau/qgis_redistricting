"""QGIS Redistricting Plugin - dataclass-like model base class

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
from reprlib import recursive_repr
from typing import Any, ClassVar, Optional, TypeVar, Union, _GenericAlias, dataclass_transform, get_type_hints

from qgis.PyQt.QtCore import QObject

from ...utils import kebab_to_camel
from .prop import MISSING, Factory, Field, FieldType, InitVar, PrivateVar, Property, field, rds_property
from .serialization import _memo, deserialize_value, kebab_dict, register_serializer, serialize_value


def _is_classvar(a_type):
    # Borrowed from `dataclasses` module
    return a_type is ClassVar or (
        type(a_type) is _GenericAlias  # pylint: disable=unidiomatic-typecheck
        and a_type.__origin__ is ClassVar
    )


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
    __fields__: dict[str, Field]

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
        for f in cls.__fields__.values():
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
                "parent", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=Optional[QObject]
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
                fld.kw_only = cls.__dataclass_transform__["kw_only_default"]  # pylint: disable=no-member

            if default_seen and default is MISSING:
                raise SyntaxError("non-default argument follows default argument")
            default_seen = default is not MISSING

            if kwonly_seen and fld.kw_only is False:
                raise SyntaxError("non-keyword argument follows keyword argument")
            kwonly_seen = fld.kw_only

            if isinstance(t, InitVar):
                fld._field_type = FieldType.INIT_VAR
                fld.serialize = False
            elif _is_classvar(t):
                fld._field_type = FieldType.CLASS_VAR
                fld.serialize = False

            flds[n] = fld

        setattr(cls, "__fields__", flds)  # noqa: B010
        setattr(cls, "__init__", wrap_init(getattr(cls, "__init__")))  # noqa: B009, B010
        if cls.__dataclass_transform__["eq_default"]:
            setattr(cls, "__eq__", compare_models)  # noqa: B010

    def __pre_init__(self): ...

    def __post_init__(self, **kwargs):  # pylint: disable=unused-argument
        ...

    def __init__(self, *args, **kwargs):  # noqa: PLR0912
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
        for f in self.__fields__.values():
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
        repr_fields = (f for f in self.__fields__.values() if f._field_type == FieldType.FIELD and f.repr)
        return f"{self.__class__.__name__}({', '.join(f'{f.name}={getattr(self, f.name)!r}' for f in repr_fields)})"


def field_dict(cls: Union[RdsBaseModel, type[RdsBaseModel]]) -> dict[str, Field]:
    if not isinstance(cls, RdsBaseModel) and not (isinstance(cls, type) and issubclass(cls, RdsBaseModel)):
        raise TypeError(f"{cls!r} is not an instance or subclass of RdsBaseModel")

    return {k: v for k, v in cls.__fields__.items() if v._field_type == FieldType.FIELD}  # pylint: disable=protected-access


def fields(cls: Union[RdsBaseModel, type[RdsBaseModel]]) -> list[Field]:
    if not isinstance(cls, RdsBaseModel) and not (isinstance(cls, type) and issubclass(cls, RdsBaseModel)):
        raise TypeError(f"{cls!r} is not an instance or subclass of RdsBaseModel")

    return [f for f in cls.__fields__.values() if f._field_type is FieldType.FIELD]  # pylint: disable=protected-access


def serialize_model(obj, memo=None, exclude_none=True):
    """Right now we just ignore already memo objects to avoid recursion.
    TODO: come up with a way to cross-reference
    """

    d = {}
    for prop in fields(obj):
        if not prop.serialize:
            continue

        if prop.fserialize is not None:
            value = prop.fserialize(getattr(obj, prop.name), memo, exclude_none)
        else:
            value = serialize_value(getattr(obj, prop.name), memo)

        if value is not _memo and (value is not None or not exclude_none):
            d[prop.name] = value

    return kebab_dict(d.items())


_ModelType = TypeVar("_ModelType", bound=RdsBaseModel)


def deserialize_model(cls: type[_ModelType], data: dict[str, Any], parent: Optional[QObject] = None) -> _ModelType:
    kw = {}

    flds = get_type_hints(cls)
    props = field_dict(cls)

    for k, v in data.items():
        f = kebab_to_camel(k)
        if f in flds:
            t = flds[f]
        else:
            continue

        if t is not None:
            if f in props and props[f].fdeserialize is not None:
                v = props[f].fdeserialize(t, v)  # noqa: PLW2901
            else:
                v = deserialize_value(t, v)  # noqa: PLW2901

        kw[f] = v

    return cls(**kw, parent=parent)


register_serializer(RdsBaseModel, serialize_model, deserialize_model)
register_serializer(RdsBaseModel, serialize_model, deserialize_model)
