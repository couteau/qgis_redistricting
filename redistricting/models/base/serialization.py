# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - serialization/deserialization functions

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
import json
import re
from functools import (
    partial,
    reduce,
    wraps
)
from io import StringIO
from types import GenericAlias
from typing import (
    Annotated,
    Any,
    Callable,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
    _GenericAlias,
    _UnionGenericAlias,
    get_args,
    get_origin,
    get_type_hints
)
from uuid import UUID

import pandas as pd
from qgis.core import (
    QgsProject,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import QObject

from .model import (
    RdsBaseModel,
    fields
)


def compose(f, *fns):
    @wraps(f)
    def inner(*args, **kwargs):
        return reduce(lambda x, fn: fn(x), fns, f(*args, **kwargs))

    return inner


serialize_dataframe = compose(partial(pd.DataFrame.to_json, orient="table"), json.loads)
deserialize_dataframe = compose(json.dumps, StringIO, partial(pd.read_json, orient="table"))


serializers = {
    UUID: str,
    QgsVectorLayer: QgsVectorLayer.id,
    pd.DataFrame: serialize_dataframe
}

deserializers = {
    UUID: UUID,
    QgsVectorLayer: QgsProject.instance().mapLayer,
    pd.DataFrame: deserialize_dataframe
}


_ST = TypeVar("_ST")


def register_serializer(dtype: Type[_ST], serializer: Callable[[_ST], Any], deserializer: Callable[[Any], _ST]):
    serializers[dtype] = serializer
    deserializers[dtype] = deserializer


def to_kebabcase(s: str):
    return re.sub(r'([A-Z])', r'-\1', s).lower()


def to_camelcase(s: str):
    f = "".join(c.capitalize() for c in s.split("-"))
    return f[0].lower() + f[1:]


def kebab_dict(kw: Iterable[tuple[str, Any]]):
    return {to_kebabcase(k): v for k, v in kw}


_memo = object()


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


def serialize_value(value, memo: dict[int, Any], exclude_none=True):
    if not id(value) in memo:
        if type(value) in serializers:
            memo[id(value)] = serializers[type(value)](value)
        elif isinstance(value, RdsBaseModel):
            memo[id(value)] = serialize_model(value, memo, exclude_none)
        elif isinstance(value, Mapping):
            memo[id(value)] = {k: serialize_value(v, memo) for k, v in value.items()}
        elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            memo[id(value)] = [serialize_value(v, memo) for v in value]
        else:
            memo[id(value)] = value

    return memo[id(value)]


def serialize(obj: Any, memo: dict[int, Any] = None, exclude_none=True):
    if memo is None:
        memo = {}

    return serialize_value(obj, memo, exclude_none)


def deserialize_iterable(value: Iterable, *args):
    if len(args) == 0:
        key_type = Any
        elem_type = Any
    elif isinstance(value, Mapping) and len(args) >= 2:
        key_type = args[0]
        elem_type = args[1]
    else:
        key_type = Any
        elem_type = args[-1]

    if not isinstance(key_type, type) or key_type is Any:
        key_type = (lambda x: x)  # pylint: disable=unnecessary-lambda-assignment

    if isinstance(elem_type, TypeVar):
        if elem_type.__bound__ is not None:
            elem_type = elem_type.__bound__
        elif elem_type.__constraints__:
            elem_type = Union[elem_type.__constraints__]
        else:
            elem_type = elem_type.__bound__ if elem_type.__bound__ is not None else type

    if isinstance(value, zip):
        value = dict(value)

    if isinstance(value, Mapping):
        value = {key_type(k): deserialize_value(elem_type, v) for k, v in value.items()}
    else:
        value = [deserialize_value(elem_type, v) for v in value]

    return value


_ModelType = TypeVar("_ModelType", bound=RdsBaseModel)


def deserialize_model(cls: Type[_ModelType], data: dict[str, Any], parent: Optional[QObject] = None) -> _ModelType:
    kw = {}

    flds = get_type_hints(cls)

    for k, v in data.items():
        f = to_camelcase(k)
        if f in flds:
            t = flds[f]
        else:
            continue

        if t is not None:
            v = deserialize_value(t, v)

        kw[f] = v

    return cls(**kw, parent=parent)


def deserialize_value(t: type, value: Any, **kw):
    if value is None:
        return None

    if isinstance(t, (_GenericAlias, GenericAlias)):
        if isinstance(t, _UnionGenericAlias):
            # type is Optional or Union
            t = get_args(t)[0]
            args = ()
        else:
            args = get_args(t)
            t = get_origin(t)
            if t is Annotated:
                t = args[0]
                args = ()
    else:
        args = ()
        cls_anns = {}

    if t in deserializers:
        try:
            value = deserializers[t](value)
        except Exception:  # pylint: disable=broad-except
            value = None
    elif issubclass(t, RdsBaseModel):
        if issubclass(t, Generic) and args:
            cls_anns = dict(zip(t.__parameters__, args))
            args = tuple(cls_anns[a] if a in cls_anns else a for a in args)
            value = deserialize_model(t[args], value, **kw)
        else:
            value = deserialize_model(t, value, **kw)
    elif issubclass(t, Mapping):
        value = t(deserialize_iterable(value, *args))
    elif issubclass(t, Iterable) and t not in (str, bytes):
        value = t(deserialize_iterable(value, *args))

    return value


T = TypeVar("T")


def deserialize(t: type[T], value: Any, **kw) -> T:
    return deserialize_value(t, value, **kw)
