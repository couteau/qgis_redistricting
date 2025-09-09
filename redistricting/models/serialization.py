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
from collections.abc import Callable, Iterable, Mapping
from functools import partial, reduce, wraps
from io import StringIO
from types import GenericAlias
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Type,
    TypeVar,
    Union,
    _GenericAlias,  # type: ignore
    _strip_annotations,  # type: ignore
    _UnionGenericAlias,  # type: ignore
    cast,
    get_args,
    get_origin,
)
from uuid import UUID

import pandas as pd
from qgis.core import QgsProject, QgsVectorLayer

from ..utils import camel_to_kebab

if TYPE_CHECKING:
    from typing_extensions import TypeAlias, TypeForm

_ST = TypeVar("_ST")


ScalarType: "TypeAlias" = Union[str, bytes, int, float, bool, None]
JSONableType: "TypeAlias" = Union[ScalarType, dict[str, "JSONableType"], list["JSONableType"], tuple["JSONableType"]]

_JSONable_contra = TypeVar("_JSONable_contra", contravariant=True)


def wrap_simple_serializer(
    f: Callable[[_ST], JSONableType],
) -> Callable[[_ST, Optional[dict[int, Any]], bool], JSONableType]:
    def wrapper(value: _ST, memo: Optional[dict[int, Any]] = None, exclude_none: bool = True):
        return f(value)

    return wrapper


def wrap_simple_deserializer(
    f: Callable[[_JSONable_contra], _ST],
) -> Callable[[type[_ST], _JSONable_contra], _ST]:
    def wrapper(cls: type[_ST], data: _JSONable_contra, **kw) -> _ST:
        return f(data)

    return wrapper


def compose(f, *fns):
    @wraps(f)
    def inner(*args, **kwargs):
        return reduce(lambda x, fn: fn(x), fns, f(*args, **kwargs))

    return inner


serialize_dataframe = compose(partial(pd.DataFrame.to_json, orient="table"), json.loads)
deserialize_dataframe = compose(json.dumps, StringIO, partial(pd.read_json, orient="table"))


serializers: dict[type, Callable[[Any, Optional[dict[int, Any]], bool], JSONableType]] = {
    datetime.datetime: wrap_simple_serializer(datetime.datetime.isoformat),
    datetime.date: wrap_simple_serializer(datetime.date.isoformat),
    datetime.time: wrap_simple_serializer(datetime.time.isoformat),
    UUID: wrap_simple_serializer(str),
    QgsVectorLayer: wrap_simple_serializer(QgsVectorLayer.id),
    pd.DataFrame: wrap_simple_serializer(serialize_dataframe),
}

deserializers: dict[type, Callable[[Union[type, _GenericAlias, GenericAlias], Any], Any]] = {
    datetime.datetime: wrap_simple_deserializer(datetime.datetime.fromisoformat),
    datetime.date: wrap_simple_deserializer(datetime.date.fromisoformat),
    datetime.time: wrap_simple_deserializer(datetime.time.fromisoformat),
    UUID: wrap_simple_deserializer(UUID),
    QgsVectorLayer: wrap_simple_deserializer(QgsProject.instance().mapLayer),  # type: ignore
    pd.DataFrame: wrap_simple_deserializer(deserialize_dataframe),
}


def register_serializer(
    dtype: Type[_ST],
    serializer: Union[
        Callable[[_ST], JSONableType],
        Callable[[_ST, Optional[dict[int, Any]], bool], JSONableType],
    ],
    deserializer: Union[Callable[[JSONableType], _ST], Callable[[type[_ST], JSONableType], _ST]],
):
    if len(inspect.signature(serializer).parameters) == 1:
        serializers[dtype] = wrap_simple_serializer(serializer)  # type: ignore
    else:
        serializers[dtype] = serializer  # type: ignore

    if len(inspect.signature(deserializer).parameters) == 1:
        deserializers[dtype] = wrap_simple_deserializer(deserializer)  # type: ignore
    else:
        deserializers[dtype] = deserializer  # type: ignore


def kebab_dict(kw: Iterable[tuple[str, Any]]):
    return {camel_to_kebab(k): v for k, v in kw}


_memo = object()


def serialize_value(value, memo: dict[int, Any], exclude_none=True):
    if id(value) not in memo:
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


def serialize(obj: Any, memo: Optional[dict[int, Any]] = None, exclude_none=True):
    if memo is None:
        memo = {}

    return serialize_value(obj, memo, exclude_none)


def deserialize_iterable(value: Iterable, *args: "TypeForm") -> Union[list, dict]:
    if len(args) == 0:
        key_type = lambda x: x  # noqa: E731 # pylint: disable=unnecessary-lambda-assignment
        elem_type = Any
    elif isinstance(value, Mapping) and len(args) > 1:
        key_type = args[0]
        elem_type = args[1]
    else:
        key_type = lambda x: x  # noqa: E731 # pylint: disable=unnecessary-lambda-assignment
        elem_type = args[-1]

    if not isinstance(key_type, type) or key_type is Any:
        key_type = lambda x: x  # noqa: E731 # pylint: disable=unnecessary-lambda-assignment

    if isinstance(elem_type, TypeVar):
        if elem_type.__bound__ is not None:
            elem_type = elem_type.__bound__
        elif elem_type.__constraints__:
            elem_type = Union[*elem_type.__constraints__]
        else:
            elem_type = type

    if isinstance(value, zip):
        value = dict(value)

    if isinstance(value, Mapping):
        value = {key_type(k): deserialize_value(elem_type, v) for k, v in value.items()}
    else:
        value = [deserialize_value(elem_type, v) for v in value]

    return value


T = TypeVar("T")


def _get_type_and_args(dtype: "TypeForm[T]", value: Any) -> tuple["TypeForm[T]", type[T], tuple[type, ...]]:
    # find base type
    args = ()
    dtype = cast("TypeForm[T]", _strip_annotations(dtype))
    t = dtype
    while not isinstance(t, type):
        args: tuple[type, ...] = get_args(t)
        if isinstance(t, _UnionGenericAlias):
            # type is Optional or Union
            if type(value) in args:
                t = type(value)
            else:
                t = args[0]
            args = ()
            dtype = cast("type[T]", t)
        else:
            t = cast("type", get_origin(t))

    return dtype, cast("type[T]", t), args


def deserialize_value(dtype: "TypeForm[T]", value: Any, **kw) -> T:
    if value is None:
        return value

    dtype, t, args = _get_type_and_args(dtype, value)

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
            if issubclass(t, Iterable) and t not in (str, bytes):
                list_items: Union[list, dict] = deserialize_iterable(value, *args)
                if type(list_items) is t:
                    value = list_items
                else:
                    constructor: Callable[[Iterable], T] = dtype if callable(dtype) else t
                    value = constructor(list_items)  # type: ignore

    return value


def deserialize(t: "TypeForm[T]", value: Any, **kw) -> T:
    return deserialize_value(t, value, **kw)
