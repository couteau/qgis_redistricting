# -*- coding: utf-8 -*-
""" QGIS Redistricting - A QGIS plugin for building districts from geographic units

        begin                : 2022-01-15
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
        git sha              : $Format:%H$

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
import os
import sys
import typing
from typing import (
    Any,
    Callable,
    TypeVar,
    Union
)

from qgis.core import QgsSettings

sys.path.insert(0, os.path.dirname(__file__))

__author__ = "Stuart C. Naifeh"
__contact__ = "stuart@cryptodira.org"
__copyright__ = "Copyright (c) 2022-2024, Stuart C. Naifeh"
__license__ = "GPLv3"
__version__ = "0.0.1"

# noinspection PyPep8Naming


class CanceledError(Exception):
    ...


class Settings:
    enableCutEdges: bool
    enableSplits: bool

    def __init__(self):
        self._settings = QgsSettings()
        self._settings.beginGroup('redistricting', QgsSettings.Section.Plugins)
        self.enableCutEdges = self._settings.value("enable_cut_edges", False, bool)
        self.enableSplits = self._settings.value("enable_split_detail", True, bool)
        self._settings.endGroup()

    def saveSettings(self):
        self._settings.beginGroup('redistricting', QgsSettings.Section.Plugins)
        self._settings.setValue("enable_cut_edges", self.enableCutEdges)
        self._settings.setValue("enable_split_detail", self.enableSplits)
        self._settings.endGroup()


settings = Settings()


# patch typing to maintain compatibility with python 3.9
if not hasattr(typing, "Self"):
    class Self:
        ...

    setattr(typing, "Self", Self)


if not hasattr(typing, "dataclass_transform"):
    T = TypeVar("T")

    def dataclass_transform(*,
                            eq_default: bool = True,
                            order_default: bool = False,
                            kw_only_default: bool = False,
                            field_specifiers: tuple[Union[type[Any], Callable[..., Any], Any]] = (),
                            **kwargs: Any,
                            ) -> Callable[[T], T]:
        def decorator(cls_or_fn):
            cls_or_fn.__dataclass_transform__ = {
                "eq_default": eq_default,
                "order_default": order_default,
                "kw_only_default": kw_only_default,
                "field_specifiers": field_specifiers,
                "kwargs": kwargs,
            }
            return cls_or_fn
        return decorator

    setattr(typing, "dataclass_transform", dataclass_transform)

if not hasattr(typing, "TypeAlias"):
    setattr(typing, "TypeAlias", type)


def classFactory(iface):  # pylint: disable=invalid-name
    """Create an instance of the Redistricting plugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .redistricting import \
        Redistricting  # pylint: disable=import-outside-toplevel
    return Redistricting(iface)
