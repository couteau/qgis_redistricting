"""QGIS Redistricting Plugin - miscellaneous utility functions

        begin                : 2024-03-20
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

import codecs
import re
from secrets import choice
from typing import Optional, Union

from qgis.core import QgsVectorLayer


def makeFieldName(expr: str, caption: Optional[str]):
    if expr.isidentifier():
        return expr

    if caption and caption.isidentifier():
        return caption.lower()

    return re.sub(r"[^\w]+", "_", (caption or expr).casefold())


def getDefaultField(layer: QgsVectorLayer, fieldList: list[Union[str, re.Pattern]]):
    for f in fieldList:
        if isinstance(f, str):
            if (i := layer.fields().lookupField(f)) != -1:
                return layer.fields()[i].name()
        elif isinstance(f, re.Pattern):
            for fld in layer.fields():
                if f.match(fld.name()):
                    return fld.name()

    return None


def matchField(field: str, layer: QgsVectorLayer, fieldList: list[Union[str, re.Pattern]]) -> bool:
    for f in fieldList:
        if isinstance(f, str):
            if field == f:
                return layer is None or layer.fields().lookupField(field) != -1
        elif isinstance(f, re.Pattern):
            if f.match(field):
                return layer is None or layer.fields().lookupField(field) != -1

    return None


DFLT_ALLOWED_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def random_id(length, allowed_chars=DFLT_ALLOWED_CHARS):
    return "".join(choice(allowed_chars) for _ in range(length))


def camel_to_snake(s: str):
    return re.sub(r"([A-Z])", r"_\1", s).lower()


def snake_to_camel(s: str):
    f = "".join(c.capitalize() for c in s.split("_"))
    return f[0].lower() + f[1:]


def camel_to_kebab(s: str):
    return re.sub(r"([A-Z])", r"-\1", s).lower()


def kebab_to_camel(s: str):
    f = "".join(c.capitalize() for c in s.split("-"))
    return f[0].lower() + f[1:]


def quote_identifier(s, errors="strict"):
    encodable = s.encode("utf-8", errors).decode("utf-8")

    nul_index = encodable.find("\x00")

    if nul_index >= 0:
        error = UnicodeEncodeError("NUL-terminated utf-8", encodable, nul_index, nul_index + 1, "NUL not allowed")
        error_handler = codecs.lookup_error(errors)
        replacement, _ = error_handler(error)
        encodable = encodable.replace("\x00", replacement)

    return '"' + encodable.replace('"', '""') + '"'


def quote_list(l: list[str]) -> list[str]:
    return [quote_identifier(s) for s in l]
