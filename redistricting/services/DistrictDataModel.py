# -*- coding: utf-8 -*-
"""Qt Model/View model for display of plan data
                              -------------------
        begin                : 2022-03-21
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
    Iterable,
    Optional,
    Sequence,
    Union
)

import numpy as np
import pandas as pd
from qgis.PyQt.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt
)
from qgis.PyQt.QtGui import (
    QBrush,
    QColor,
    QFont
)

from ..models import (
    BaseDeviationValidator,
    DeviationType,
    DistrictColumns,
    MaxDeviationValidator,
    MetricsColumns,
    PlusMinusDeviationValidator,
    RdsDistrict,
    RdsPlan
)
from .PlanColors import getColorForDistrict


class RdsDistrictDataModel(QAbstractTableModel):
    RawDataRole = Qt.UserRole + 2

    _plan: RdsPlan = None

    def __init__(self, plan: RdsPlan = None, parent: QObject = None):
        super().__init__(parent)
        self._keys = []
        self._headings = []
        self._plan = None
        self._districts: Sequence[RdsDistrict] = []
        self._validator: BaseDeviationValidator = None
        self.plan = plan

    @property
    def plan(self) -> RdsPlan:
        return self._plan

    def updatePlanFields(self):
        self.beginResetModel()
        self._keys = list(DistrictColumns)
        self._headings = [s.comment for s in DistrictColumns]

        for field in self._plan.popFields:
            self._keys.append(field.fieldName)
            self._headings.append(field.caption)

        for field in self._plan.dataFields:
            fn = field.fieldName
            if field.sumField:
                self._keys.append(fn)
                self._headings.append(field.caption)
            if field.pctBase and (field.pctBase == self._plan.popField or field.pctBase in self._keys):
                self._keys.append(f"pct_{fn}")
                self._headings.append(f"%{field.caption}")

        self._keys.extend(MetricsColumns.CompactnessScores())
        self._headings.extend([s.comment for s in MetricsColumns.CompactnessScores()])  # pylint: disable=no-member
        self.endResetModel()

    @plan.setter
    def plan(self, value: RdsPlan):
        self.beginResetModel()

        if self._plan is not None:
            self._plan.districtDataChanged.disconnect(self.districtChanged)
            self._plan.dataFieldsChanged.disconnect(self.updatePlanFields)
            self._plan.popFieldsChanged.disconnect(self.updatePlanFields)
            self._plan.deviationChanged.disconnect(self.deviationChanged)
            self._plan.deviationTypeChanged.disconnect(self.deviationTypeChanged)
            self._plan.districtAdded.disconnect(self.districtListChanged)
            self._plan.districtRemoved.disconnect(self.districtListChanged)

        self._plan = value
        if self._plan:
            self._districts = self._plan.districts
            self.updatePlanFields()
            self._validator = PlusMinusDeviationValidator(self._plan) \
                if self._plan.deviationType == DeviationType.OverUnder \
                else MaxDeviationValidator(self._plan)
            self._plan.districtDataChanged.connect(self.districtChanged)
            self._plan.dataFieldsChanged.connect(self.updatePlanFields)
            self._plan.popFieldsChanged.connect(self.updatePlanFields)
            self._plan.deviationChanged.connect(self.deviationChanged)
            self._plan.deviationTypeChanged.connect(self.deviationTypeChanged)
            self._plan.districtAdded.connect(self.districtListChanged)
            self._plan.districtRemoved.connect(self.districtListChanged)
        else:
            self._districts = []
            self._keys = []
            self._headings = []

        self.endResetModel()

    def deviationChanged(self):
        self.dataChanged.emit(self.createIndex(1, 1), self.createIndex(self.rowCount() - 1, 4), [Qt.BackgroundRole])

    def deviationTypeChanged(self):
        self._validator = PlusMinusDeviationValidator() if self._plan.deviationType == DeviationType.OverUnder else MaxDeviationValidator()
        self.dataChanged.emit(self.createIndex(1, 1), self.createIndex(self.rowCount() - 1, 4), [Qt.BackgroundRole])

    def districtListChanged(self):
        self.beginResetModel()
        self.endResetModel()

    def districtChanged(self, district: RdsDistrict):
        row = self._districts.index(district)
        start = self.createIndex(row, 1)
        end = self.createIndex(row, self.columnCount())
        self.dataChanged.emit(start, end, {Qt.DisplayRole, Qt.EditRole, Qt.BackgroundRole})

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._districts) if self._districts and not parent.isValid() else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or self._districts is None:
            return 0

        return len(self._keys)

    def data(self, index, role=Qt.DisplayRole):
        value = None
        try:
            row = index.row()
            col = index.column()
            district = self._districts[row]

            if role in (Qt.DisplayRole, Qt.EditRole, RdsDistrictDataModel.RawDataRole):
                key = self._keys[col]
                if key[:3] == 'pct' and key != 'pct_deviation':
                    pctbase = self._plan.dataFields[key[4:]].pctBase
                    if pctbase == self._plan.popField:
                        pctbase = DistrictColumns.POPULATION
                    if pctbase in self._keys and district[pctbase] != 0:
                        value = district[key[4:]] / district[pctbase]
                    else:
                        value = None
                else:
                    value = district[key]

                if pd.isna(value):
                    return None

                if role != RdsDistrictDataModel.RawDataRole:
                    if district.district == 0:
                        if key == 'district':
                            value = district.name
                        elif key == 'name':
                            value = None

                    if key == 'deviation':
                        value = f'{value:+,}'
                    elif key == 'pct_deviation':
                        value = f'{value:+.2%}'
                    elif key in MetricsColumns.CompactnessScores():
                        value = f'{value:0.3}'
                    elif key[:3] == 'pct':
                        value = f'{value:.2%}'
                    elif isinstance(value, (int, np.integer)):
                        value = f'{value:,}'
                    elif isinstance(value, (float, np.floating)):
                        value = f'{value:,.2f}'

            elif role == Qt.BackgroundRole:
                if col == 0 or district.district == 0:
                    color = getColorForDistrict(self._plan, district.district)
                    value = QBrush(color)
                elif 3 <= col <= 5:
                    if self._validator.validateDistrict(district):
                        color = QColor(0x60, 0xbd, 0x63)  # QColor(99, 196, 101)  # 60be63ff
                        value = QBrush(color)

            elif role == Qt.FontRole:
                row = index.row()
                col = index.column()
                if row > 0 and col in {0, 4, 5}:
                    value = QFont()
                    value.setBold(True)

            elif role == Qt.TextAlignmentRole:
                if index.column() == 0:
                    value = Qt.AlignCenter

            elif role == Qt.TextColorRole:
                row = index.row()
                col = index.column()
                if col == 0 or district.district == 0:
                    value = QColor(55, 55, 55)

        except Exception as e:  # pylint: disable=broad-exception-caught, unused-variable
            return None

        return value

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        if role == Qt.EditRole and index.column() == 1 and index.row() != 0:
            dist = self._districts[index.row()]
            dist.name = value
            self.dataChanged.emit(index, index, {Qt.DisplayRole})
            return True

        return False

    def headerData(self, section, orientation: Qt.Orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal and section < len(self._headings):
            return self._headings[section]

        return None

    def flags(self, index):
        f = super().flags(index)
        if index.column() == 1 and index.row() != 0:
            f |= Qt.ItemIsEditable

        return f

    def districtsUpdated(self, plan: RdsPlan, districts: Union[Iterable[int], None]):
        if plan != self._plan:
            return

        if districts:
            for d in districts:
                self.dataChanged.emit(
                    self.createIndex(d, 3),
                    self.createIndex(d, self.columnCount()),
                    [Qt.DisplayRole, Qt.EditRole]
                )
                self.dataChanged.emit(self.createIndex(d, 4), self.createIndex(d, 5), [Qt.FontRole])
        else:
            self.beginResetModel()
            self.endResetModel()


class RdsDistrictFilterFieldsProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._demographics: bool = True
        self._metrics: bool = True

    @property
    def districtModel(self) -> RdsDistrictDataModel:
        return self.sourceModel()

    def showDemographics(self, show: bool = True):
        if show != self._demographics:
            self._demographics = show
            self.invalidateFilter()

    def showMetrics(self, show: bool = True):
        if show != self._metrics:
            self._metrics = show
            self.invalidateFilter()

    def filterAcceptsColumn(self, source_column: int, source_parent: QModelIndex) -> bool:  # pylint: disable=unused-argument
        name = self.districtModel._keys[source_column]  # pylint: disable=protected-access
        return name in DistrictColumns or name in {f.fieldName for f in self.districtModel.plan.popFields} or (self._metrics and name in MetricsColumns) or (self._demographics and name not in MetricsColumns)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Keep 'Unassigned' row at the top no matter what the sort order is"""
        if self.districtModel._districts[right.row()].district == 0:  # pylint: disable=protected-access
            return self.sortOrder() == Qt.DescendingOrder
        if self.districtModel._districts[left.row()].district == 0:  # pylint: disable=protected-access
            return self.sortOrder() == Qt.AscendingOrder

        return super().lessThan(left, right)
