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
from qgis.PyQt.QtGui import (
    QStandardItem,
    QStandardItemModel
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QWidget
)

from ..core import (
    GeoField,
    RedistrictingPlan
)
from ..core.PlanSplitsModel import SplitsModel
from ..core.utils import tr
from .ui.DlgSplits import Ui_dlgSplits


class DlgSplitDetail(Ui_dlgSplits, QDialog):
    def __init__(self, plan: RedistrictingPlan, geoField: GeoField, parent: Optional[QWidget] = None, flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.Dialog):
        super().__init__(parent, flags)
        self.setupUi(self)

        self._model = None
        self._plan: RedistrictingPlan = None
        self._field: GeoField = None

        self.plan = plan
        self.geoField = geoField

    def makeModel(self):
        if self._plan is None or self._field is None:
            model = QStandardItemModel(0, 0, self)
            return model

        # headings = [self._field.nameField.caption] if self._field.nameField else []
        headings = []
        headings.extend([
            self._field.caption,
            tr('Districts')
        ])
        h = True

        model = QStandardItemModel()

        root = model.invisibleRootItem()
        for s in self._plan.stats.splits[self._field]:
            row: list[QStandardItem] = []
#            if self._field.nameField:
#                row.append(QStandardItem(s[self._field.nameField.fieldName]))

            if s.get('name'):
                f = f'{s["name"]} ({s[self._field.fieldName]})'
            else:
                f = s[self._field.fieldName]
            row.append(QStandardItem(f))
            if isinstance(s["districts"], dict):
                row.append(QStandardItem(','.join(d for d in s["districts"].keys())))
            else:
                row.append(QStandardItem(districts=s["districts"]))
            root.appendRow(row)
            if isinstance(s["districts"], dict):
                if h:
                    headings.append(tr('Population'))
                for district, pop in s["districts"].items():
                    children = [QStandardItem(""), QStandardItem(
                        district), QStandardItem(f"{pop[self._plan.popField]:,}")]

                    for field in self._plan.popFields:
                        v = pop[field.fieldName]
                        children.append(QStandardItem(f"{v if v is not None else 0:,}"))
                        if h:
                            headings.append(field.caption)
                    for field in self._plan.dataFields:
                        v = pop[field.fieldName]
                        if field.sum:
                            children.append(QStandardItem(f"{v if v is not None else 0:,}"))
                            if h:
                                headings.append(field.caption)
                        if field.pctbase is not None:
                            if field.pctbase == self._plan.popField:
                                base = pop[self.plan.popField]
                            else:
                                continue

                            if base != 0:
                                pct = v / pop[self.plan.popField]
                            else:
                                pct = 0

                            children.append(QStandardItem(f"{pct:.2%}"))
                            if h:
                                headings.append(f'%{field.caption}')
                    h = False
                    row[0].appendRow(children)

        model.setHorizontalHeaderLabels(headings)
        return model

    @property
    def plan(self) -> RedistrictingPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RedistrictingPlan):
        self._plan = value
        if self._plan and self._field:
            # self._model = self.makeModel()
            self._model = SplitsModel(self._plan.districts.splits[self._field], self)
        else:
            self._model = None
        self.tvSplits.setModel(self._model)

    @property
    def geoField(self) -> GeoField:
        return self._field

    @geoField.setter
    def geoField(self, value: GeoField):
        self._field = value
        if self._plan and self._field:
            # self._model = self.makeModel()
            self._model = SplitsModel(self._plan.districts.splits[self._field], self)
        else:
            self._model = None

        self.tvSplits.setModel(self._model)

        if self._field:
            self.setWindowTitle(f"{self._field.caption} {tr('Splits')}")
