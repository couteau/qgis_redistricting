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
from .lists import (
    KeyedList,
    KeyedListFactory,
    SortedKeyedList
)
from .model import (
    MISSING,
    Factory,
    PrivateVar,
    Property,
    RdsBaseModel,
    field,
    fields,
    in_range,
    make_accessor,
    not_empty,
    rds_property,
    set_list
)
from .serialize import (
    deserialize,
    serialize
)
