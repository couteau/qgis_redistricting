# -*- coding: utf-8 -*-
"""Qt Model/View model for selecting geography when painting districts

        begin                : 2022-05-03
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
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
from typing import (
    Any,
    Optional
)

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    Qt,
    QVariant
)

from .Field import Field
from .Plan import RedistrictingPlan
from .utils import tr


class GeoFieldsModel(QAbstractListModel):
    def __init__(self, plan: RedistrictingPlan, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._data: list[Field] = list(plan.geoFields)
        self._data.insert(0, Field(plan.assignLayer, plan.geoIdField,
                          False, plan.geoIdCaption, self))

    def rowCount(self, parent: QModelIndex = ...) -> int:  # pylint: disable=unused-argument
        return len(self._data)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        row = index.row()

        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._data[row].caption
        if role == Qt.DecorationRole:
            return QgsApplication.getThemeIcon('/mIconVector.svg')

        return QVariant()

    @property
    def fields(self):
        return self._data

class PopFieldsModel(QAbstractListModel):
    def __init__(self, plan: RedistrictingPlan, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._data: list[Field] = list(plan.popFields)
        self._data.insert(0, Field(plan.popLayer, plan.popField,
                          False, tr("Total Population"), self))

    def rowCount(self, parent: QModelIndex = ...) -> int:  # pylint: disable=unused-argument
        return len(self._data)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        row = index.row()

        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._data[row].caption
        if role == Qt.DecorationRole:
            return QgsApplication.getThemeIcon('/mIconVector.svg')

        return QVariant()

    @property
    def fields(self):
        return self._data
