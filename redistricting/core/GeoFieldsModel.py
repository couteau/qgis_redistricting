# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DlgEditPlan
        QGIS Redistricting Plugin - List model for selecting geo fields
                              -------------------
        begin                : 2022-05-03
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 * *
 *   This program is free software; you can redistribute it and / or modify *
 *   it under the terms of the GNU General Public License as published by *
 *   the Free Software Foundation; either version 2 of the License, or *
 *   (at your option) any later version. *
 * *
 ***************************************************************************/
"""
from typing import Optional, Any
from qgis.PyQt.QtCore import QObject, QVariant, Qt, QAbstractListModel, QModelIndex
from qgis.core import QgsApplication
from . import RedistrictingPlan, Field


class GeoFieldsModel(QAbstractListModel):
    def __init__(self, plan: RedistrictingPlan, parent: Optional[QObject] = ...) -> None:
        super().__init__(parent)
        self._data = list(plan.geoFields)
        self._data.insert(0, Field(plan.assignLayer, plan.geoIdField,
                          False, plan.geoDisplay, self))

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
