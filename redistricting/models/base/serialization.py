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
import datetime
import inspect
import json
import logging
import re
from functools import (
    partial,
    reduce,
    wraps
)
from io import StringIO
from types import GenericAlias
from typing import (
    Any,
    Callable,
    Iterable,
    Mapping,
    Type,
    TypeVar,
    Union,
    _GenericAlias,
    _strip_annotations,
    _UnionGenericAlias,
    get_args,
    get_origin
)
from uuid import UUID

import pandas as pd
from qgis.core import (
    QgsProject,
    QgsVectorLayer
)

_ST = TypeVar("_ST")

ScalarType = Union[str, bytes, int, float, bool, None]
JSONableType = Union[ScalarType, dict[str, "JSONableType"], list["JSONableType"], tuple["JSONableType"]]
SimpleSerializeFunction = Callable[[_ST], JSONableType]
SerializerFunction = Callable[[_ST, dict[int, Any], bool], JSONableType]
SimpleDeserializeFunction = Callable[[JSONableType], _ST]
DeserializerFunction = Callable[[type, JSONableType, Any], _ST]


def wrap_simple_serializer(f):
    def wrapper(value: Any, memo: dict[int, Any] = None, exclude_none: bool = True):  # pylint: disable=unused-argument
        return f(value)

    return wrapper


def wrap_simple_deserializer(f):
    def wrapper(cls, data: Any, **kw):  # pylint: disable=unused-argument
        return f(data)
    return wrapper


def compose(f, *fns):
    @wraps(f)
    def inner(*args, **kwargs):
        return reduce(lambda x, fn: fn(x), fns, f(*args, **kwargs))

    return inner


serialize_dataframe = compose(partial(pd.DataFrame.to_json, orient="table"), json.loads)
deserialize_dataframe = compose(json.dumps, StringIO, partial(pd.read_json, orient="table"))


serializers: dict[type, SerializerFunction] = {
    datetime.datetime: wrap_simple_serializer(datetime.datetime.isoformat),
    datetime.date: wrap_simple_serializer(datetime.date.isoformat),
    datetime.time: wrap_simple_serializer(datetime.time.isoformat),
    UUID: wrap_simple_serializer(str),
    QgsVectorLayer: wrap_simple_serializer(QgsVectorLayer.id),
    pd.DataFrame: wrap_simple_serializer(serialize_dataframe)
}

deserializers: dict[type, DeserializerFunction] = {
    datetime.datetime: wrap_simple_deserializer(datetime.datetime.fromisoformat),
    datetime.date: wrap_simple_deserializer(datetime.date.fromisoformat),
    datetime.time: wrap_simple_deserializer(datetime.time.fromisoformat),
    UUID: wrap_simple_deserializer(UUID),
    QgsVectorLayer: wrap_simple_deserializer(QgsProject.instance().mapLayer),
    pd.DataFrame: wrap_simple_deserializer(deserialize_dataframe)
}


def register_serializer(
    dtype: Type[_ST],
    serializer: Union[SimpleSerializeFunction[_ST], SerializerFunction[_ST]],
    deserializer: Union[SimpleDeserializeFunction[_ST], DeserializerFunction[_ST]]
):
    if len(inspect.signature(serializer).parameters) == 1:
        serializers[dtype] = wrap_simple_serializer(serializer)
    else:
        serializers[dtype] = serializer

    if len(inspect.signature(deserializer).parameters) == 1:
        deserializers[dtype] = wrap_simple_deserializer(deserializer)
    else:
        deserializers[dtype] = deserializer


def camel_to_snake(s: str):
    return re.sub(r'([A-Z])', r'_\1', s).lower()


def snake_to_camel(s: str):
    f = "".join(c.capitalize() for c in s.split("_"))
    return f[0].lower() + f[1:]


def camel_to_kebab(s: str):
    return re.sub(r'([A-Z])', r'-\1', s).lower()


def kebab_to_camel(s: str):
    f = "".join(c.capitalize() for c in s.split("-"))
    return f[0].lower() + f[1:]


def kebab_dict(kw: Iterable[tuple[str, Any]]):
    return {camel_to_kebab(k): v for k, v in kw}


_memo = object()


def serialize_value(value, memo: dict[int, Any], exclude_none=True):
    if not id(value) in memo:
        if type(value) in serializers:
            memo[id(value)] = serializers[type(value)](value, memo, exclude_none)
        else:
            for t, serializer in serializers.items():
                if issubclass(type(value), t):
                    memo[id(value)] = serializer(value, memo, exclude_none)
                    break
            else:
                if isinstance(value, Mapping):
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


def deserialize_value(dtype: type, value: Any, **kw):
    if value is None:
        return None

    # find base type
    args = ()
    dtype = t = _strip_annotations(dtype)
    while isinstance(t, (_GenericAlias, GenericAlias)):
        args = get_args(t)
        if isinstance(t, _UnionGenericAlias):
            # type is Optional or Union
            if type(value) in args:
                t = type(value)
            else:
                t = args[0]
            args = ()
            dtype = t
        else:
            t = get_origin(t)

    if t in deserializers:
        # if the exact type is in the deserializers dict, use the deserializer for that type
        value = deserializers[t](dtype, value, **kw)
    else:
        # search for a superclass of the type
        for s, deserializer in deserializers.items():
            if issubclass(t, s):
                try:
                    value = deserializer(dtype, value, **kw)
                except Exception as e:  # pylint: disable=broad-except
                    logging.error(e)
                    value = None
                break
        else:
            if issubclass(t, Mapping):
                value = dtype(deserialize_iterable(value, *args))
            elif issubclass(t, Iterable) and t not in (str, bytes):
                value = dtype(deserialize_iterable(value, *args))

    return value


T = TypeVar("T")


def deserialize(t: type[T], value: Any, **kw) -> T:
    return deserialize_value(t, value, **kw)
