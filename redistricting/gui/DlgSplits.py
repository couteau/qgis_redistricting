# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Import Assignments Dialog

        begin                : 2022-01-15
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
    Optional,
    Union
)

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QWidget
)

from ..models import (
    RdsGeoField,
    RdsPlan
)
from ..services import RdsSplitsModel
from ..utils import tr
from .ui.DlgSplits import Ui_dlgSplits


class DlgSplitDetail(Ui_dlgSplits, QDialog):
    def __init__(
            self,
            plan: RdsPlan,
            geoField: RdsGeoField,
            parent: Optional[QWidget] = None,
            flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.Dialog
    ):
        super().__init__(parent, flags)
        self.setupUi(self)

        self._model = None
        self._plan: RdsPlan = None
        self._field: RdsGeoField = None

        self.plan = plan
        self.geoField = geoField
        self.cmbGeography.currentIndexChanged.connect(self.geographyChanged)

    @property
    def plan(self) -> RdsPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RdsPlan):
        if self._plan:
            self.plan.nameChanged.disconnect(self.planNameChanged)
            self.plan.geoFieldsChanged.disconnect(self.updateGeography)
            if self._model:
                self.tvSplits.expanded.disconnect(self._model.setExpanded)
                self.tvSplits.collapsed.disconnect(self._model.setCollapsed)

        self._plan = value

        if self._plan:
            if self._field:
                self._model = RdsSplitsModel(self._plan, self._plan.metrics.splits[self._field], self)
                self.tvSplits.expanded.connect(self._model.setExpanded)
                self.tvSplits.collapsed.connect(self._model.setCollapsed)
            else:
                self._model = None
            self.lblPlan.setText(self._plan.name)
            self.updateGeography()
            self.plan.nameChanged.connect(self.planNameChanged)
            self.plan.geoFieldsChanged.connect(self.updateGeography)

        self.tvSplits.setModel(self._model)

    @property
    def geoField(self) -> RdsGeoField:
        return self._field

    @geoField.setter
    def geoField(self, value: RdsGeoField):
        self._field = value
        if self._model:
            self.tvSplits.expanded.disconnect(self._model.setExpanded)
            self.tvSplits.collapsed.disconnect(self._model.setCollapsed)

        if self._plan and self._field:
            self._model = RdsSplitsModel(self._plan, self._plan.metrics.splits[self._field.field], self)
            self.tvSplits.expanded.connect(self._model.setExpanded)
            self.tvSplits.collapsed.connect(self._model.setCollapsed)
        else:
            self._model = None

        self.tvSplits.setModel(self._model)

        if self._field:
            self.setWindowTitle(f"{self._field.caption} {tr('Splits')}")
            self.cmbGeography.setCurrentText(self._field.caption)

    def geographyChanged(self, index):
        self.geoField = self.plan.geoFields[index]

    def planNameChanged(self):
        self.lblPlan.setText(self._plan.name)

    def updateGeography(self):
        self.cmbGeography.clear()
        self.cmbGeography.addItems([f.caption for f in self._plan.geoFields])
