# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - table model wrapping a list of district deltas

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022-2024 by Cryptodira
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
import textwrap
from dataclasses import dataclass
from enum import IntEnum
from typing import (
    Any,
    Iterable,
    List,
    Optional,
    Sequence,
    Union
)

import numpy as np
import pandas as pd
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    QAbstractItemModel,
    QAbstractListModel,
    QAbstractTableModel,
    QMimeData,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    QVariant
)
from qgis.PyQt.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPixmap
)

from ..utils import tr
from .colors import getColorForDistrict
from .columns import (
    DistrictColumns,
    FieldCategory,
    FieldColors,
    MetricsColumns
)
from .delta import DeltaList
from .district import RdsDistrict
from .field import (
    RdsDataField,
    RdsField
)
from .plan import (
    DeviationType,
    RdsMetrics,
    RdsPlan
)
from .splits import (
    RdsSplitBase,
    RdsSplitDistrict,
    RdsSplitGeography,
    RdsSplits
)
from .validators import (
    BaseDeviationValidator,
    MaxDeviationValidator,
    PlusMinusDeviationValidator
)


@ dataclass
class DistrictColumnData:
    key: str
    heading: str
    category: FieldCategory


class RdsDistrictDataModel(QAbstractTableModel):
    RawDataRole = Qt.UserRole + 2

    _plan: RdsPlan = None

    def __init__(self, plan: RdsPlan = None, parent: QObject = None):
        super().__init__(parent)
        self._columns: list[DistrictColumnData] = []
        self._plan = None
        self._districts: Sequence[RdsDistrict] = []
        self._validator: BaseDeviationValidator = None
        self.plan = plan

    @ property
    def plan(self) -> RdsPlan:
        return self._plan

    def updatePlanFields(self):
        self.beginResetModel()
        self._columns = [DistrictColumnData(d, d.comment, FieldCategory.Population)
                         for d in DistrictColumns
                         if d != DistrictColumns.DISTRICT]
        self._columns[0].heading = DistrictColumns.DISTRICT.comment  # pylint: disable=no-member
        self._columns.extend(DistrictColumnData(field.fieldName, field.caption, field.category)
                             for field in self._plan.popFields)

        for field in self._plan.dataFields:
            fn = field.fieldName
            if field.sumField:
                self._columns.append(DistrictColumnData(field.fieldName, field.caption, field.category))
            if field.pctBase is not None:
                self._columns.append(DistrictColumnData(f"pct_{fn}", f"%{field.caption}", field.category))

        self._columns.extend(DistrictColumnData(c, c.comment, FieldCategory.Metrics)  # pylint: disable=no-member
                             for c in MetricsColumns.CompactnessScores())

        self.endResetModel()

    @ plan.setter
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
            self._columns = []

        self.endResetModel()

    def deviationChanged(self):
        self.dataChanged.emit(self.createIndex(1, 1), self.createIndex(self.rowCount() - 1, 4), [Qt.BackgroundRole])

    def deviationTypeChanged(self):
        self._validator = PlusMinusDeviationValidator() \
            if self._plan.deviationType == DeviationType.OverUnder \
            else MaxDeviationValidator()
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

        return len(self._columns)

    def data(self, index, role=Qt.DisplayRole):
        value = None
        try:
            row = index.row()
            col = index.column()
            key = self._columns[col].key
            district = self._districts[row]

            if role in (Qt.DisplayRole, Qt.EditRole, RdsDistrictDataModel.RawDataRole):
                if key[:3] == 'pct' and key != 'pct_deviation':
                    pctbase = self._plan.dataFields[key[4:]].pctBase
                    if pctbase == self._plan.popField:
                        pctbase = DistrictColumns.POPULATION
                    if district[pctbase] != 0:
                        value = district[key[4:]] / district[pctbase]
                    else:
                        value = None
                else:
                    value = district[key]

                if pd.isna(value):
                    return None

                if role != RdsDistrictDataModel.RawDataRole:
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
                elif col in {DistrictColumns.POPULATION, DistrictColumns.DEVIATION, DistrictColumns.PCT_DEVIATION}:
                    if self._validator.validateDistrict(district):
                        color = QColor(0x60, 0xbd, 0x63)  # QColor(99, 196, 101)  # 60be63ff
                        value = QBrush(color)

            elif role == Qt.FontRole:
                # bold for district name and deviations (except for the unassigned row)
                if col == 0 or (
                        district.district != 0 and
                        key in {DistrictColumns.DEVIATION, DistrictColumns.PCT_DEVIATION}
                ):
                    value = QFont()
                    value.setBold(True)

            elif role == Qt.TextAlignmentRole:
                if col == 0:
                    value = Qt.AlignCenter
                else:
                    value = Qt.AlignRight

            elif role == Qt.TextColorRole:
                if col == 0 or district.district == 0:
                    value = QColor(55, 55, 55)

        except Exception as e:  # pylint: disable=broad-exception-caught, unused-variable
            return None

        return value

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        if role == Qt.EditRole and self._columns[index.column()].key == DistrictColumns.NAME and index.row() != 0:
            dist = self._districts[index.row()]
            dist.name = value
            self.dataChanged.emit(index, index, {Qt.EditRole})
            return True

        return False

    def headerData(self, section, orientation: Qt.Orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal and section < len(self._columns):
            return self._columns[section].heading

        return None

    def flags(self, index):
        f = super().flags(index)
        if self._columns[index.column()].key == DistrictColumns.NAME and index.row() != 0:
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
        self._filtercats: set[FieldCategory] = set(FieldCategory)

    @ property
    def districtModel(self) -> RdsDistrictDataModel:
        return self.sourceModel()

    def toggleCategory(self, cat: FieldCategory):
        if cat in self._filtercats:
            self._filtercats.remove(cat)
        else:
            self._filtercats.add(cat)
        self.invalidateFilter()

    def showCategory(self, cat: FieldCategory, show: bool = True):
        if show == (cat in self._filtercats):
            return

        self.toggleCategory(cat)

    def showDemographics(self, show: bool = True):
        self.showCategory(FieldCategory.Demographic, show)

    def showMetrics(self, show: bool = True):
        self.showCategory(FieldCategory.Metrics, show)

    def filterAcceptsColumn(self, source_column: int, source_parent: QModelIndex) -> bool:  # pylint: disable=unused-argument
        # pylint: disable=protected-access
        if self.districtModel._columns[source_column].key == 'members':
            return self.districtModel._plan.numDistricts != self.districtModel._plan.numDistricts

        cat = self.districtModel._columns[source_column].category
        return cat in self._filtercats

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Keep 'Unassigned' row at the top no matter what the sort order is"""
        if self.districtModel._districts[right.row()].district == 0:  # pylint: disable=protected-access
            return self.sortOrder() == Qt.DescendingOrder
        if self.districtModel._districts[left.row()].district == 0:  # pylint: disable=protected-access
            return self.sortOrder() == Qt.AscendingOrder

        return super().lessThan(left, right)


class DistrictSelectModel(QAbstractListModel):
    def __init__(self, plan: RdsPlan, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = plan
        self._plan.districtAdded.connect(self.updateDistricts)
        self._plan.districtRemoved.connect(self.updateDistricts)
        self._plan.districtDataChanged.connect(self.districtNameChanged)
        self._districts = plan.districts
        self._offset = 2

    def updateDistricts(self):
        self.beginResetModel()
        self.endResetModel()

    def districtNameChanged(self, district: RdsDistrict):
        idx = self._districts.index(district)
        index = self.createIndex(idx + self._offset, 0)
        self.dataChanged.emit(index, index, {Qt.DisplayRole})

    def indexFromDistrict(self, district):
        if district in self._districts:
            i = self._districts.index(district)
            return 1 if i == 0 else i + self._offset

        return 0

    def districtFromIndex(self, index: int):
        if index < self._offset:
            dist = self._districts[0] if index == 1 else None
        elif index > self._offset:
            dist = self._districts[index-2]

        return dist

    def rowCount(self, parent: QModelIndex):  # pylint: disable=unused-argument
        return len(self._districts) + self._offset

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        row = index.row()

        if role in {Qt.DisplayRole, Qt.EditRole}:
            if row == 0:
                return tr('All')

            if row == 1:
                return self._districts[0].name

            if row > self._offset:
                return self._districts[row - self._offset].name

        if role == Qt.DecorationRole:
            if row == 0:
                return QgsApplication.getThemeIcon('/mActionSelectAll.svg')

            if row == 1 or row > self._offset:
                dist = 0 if row == 1 else row-self._offset
                color = getColorForDistrict(self._plan, self._districts[dist].district)
                pixmap = QPixmap(64, 64)
                pixmap.fill(Qt.transparent)
                p = QPainter()
                if p.begin(pixmap):
                    p.setPen(color)
                    p.setBrush(QBrush(color))
                    p.drawEllipse(0, 0, 64, 64)
                    p.end()
                else:
                    pixmap.fill(color)
                return QIcon(pixmap)

        if role == Qt.AccessibleDescriptionRole and row == self._offset:
            return 'separator'

        return QVariant()

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index)
        if index.row() == self._offset:
            flags = flags & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable
        return flags


class SourceDistrictModel(DistrictSelectModel):
    def __init__(self, plan: RdsPlan, parent: Optional[QObject] = None):
        super().__init__(plan, parent)
        self._plan = plan
        self._offset = 3

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        row = index.row()

        if row == 2:
            if role in {Qt.DisplayRole, Qt.EditRole}:
                return tr('Selected')
            if role == Qt.DecorationRole:
                return QgsApplication.getThemeIcon('/mActionProcessSelected.svg')

        return super().data(index, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index)
        if index.row() == 2 and \
                self._plan.assignLayer.selectedFeatureCount() == 0 and \
                self._plan.popLayer.selectedFeatureCount() == 0 and \
                self._plan.geoLayer.selectedFeatureCount() == 0:
            flags = flags & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable
        return flags


class TargetDistrictModel(DistrictSelectModel):
    def data(self, index: QModelIndex, role: int = ...) -> Any:
        row = index.row()

        if role == Qt.DisplayRole or role == Qt.EditRole:
            if row == 0:
                return tr('Select district')

        elif role == Qt.DecorationRole:
            if row == 0:
                return QgsApplication.getThemeIcon('/mActionToggleEditing.svg')

        return super().data(index, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index)
        if index.row() == 0:
            flags = flags & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable
        return flags


class DeltaListModel(QAbstractTableModel):
    FieldTypeRole = Qt.UserRole + 1

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = None
        self._fields = []
        self._delta: DeltaList = None

    @property
    def plan(self):
        return self._plan

    def setPlan(self, plan: RdsPlan, delta: DeltaList):
        if plan != self._plan:
            if self._plan is not None:
                self._plan.popFieldChanged.disconnect(self.updateFields)
                self._plan.popFieldsChanged.disconnect(self.updateFields)
                self._plan.dataFieldsChanged.disconnect(self.updateFields)

            self._plan = plan

            if self._plan is not None:
                self._plan.popFieldChanged.connect(self.updateFields)
                self._plan.popFieldsChanged.connect(self.updateFields)
                self._plan.dataFieldsChanged.connect(self.updateFields)
                self.updateFields()
            else:
                self._fields = []

            self.setDelta(delta)

    def setDelta(self, delta: DeltaList):
        if delta != self._delta:
            self.beginResetModel()
            if self._delta is not None:
                self._delta.updateStarted.disconnect(self.startUpdate)
                self._delta.updateComplete.disconnect(self.endUpdate)

            self._delta = delta

            if self._delta is not None:
                self._delta.updateStarted.connect(self.startUpdate)
                self._delta.updateComplete.connect(self.endUpdate)
            self.endResetModel()

    def updateFields(self):
        self._fields = [
            {
                'name': f'new_{DistrictColumns.POPULATION}',
                'caption': DistrictColumns.POPULATION.comment,  # pylint: disable=no-member
                'format': '{:,.0f}',
                'field-type': FieldCategory.Population
            },
            {
                'name': DistrictColumns.POPULATION,
                'caption': f'{DistrictColumns.POPULATION.comment} - {tr("Change")}',  # pylint: disable=no-member
                'format': '{:+,.0f}',
                'field-type': FieldCategory.Population
            },
            {
                'name': DistrictColumns.DEVIATION,
                'caption': DistrictColumns.DEVIATION.comment,  # pylint: disable=no-member
                'format': '{:,.0f}',
                'field-type': FieldCategory.Population
            },
            {
                'name': DistrictColumns.PCT_DEVIATION,
                'caption': DistrictColumns.PCT_DEVIATION.comment,  # pylint: disable=no-member
                'format': '{:+.2%}',
                'field-type': FieldCategory.Population
            }
        ]

        field: RdsField
        for field in self._plan.popFields:
            fn = field.fieldName
            self._fields.extend([
                {
                    'name': f'new_{fn}',
                    'caption': field.caption,
                    'format': '{:,.0f}',
                    'field-type': field.category
                },
                {
                    'name': fn,
                    'caption': f'{field.caption} - {tr("Change")}',
                    'format': '{:+,.0f}',
                    'field-type': field.category
                }
            ])

        field: RdsDataField
        for field in self._plan.dataFields:
            fn = field.fieldName
            if field.sumField:
                self._fields.extend([
                    {
                        'name': f'new_{fn}',
                        'caption': field.caption,
                        'format': '{:,.0f}',
                        'field-type': field.category
                    },
                    {
                        'name': fn,
                        'caption': field.caption + ' - ' + tr('Change'),
                        'format': '{:+,.0f}',
                        'field-type': field.category
                    }
                ])

            if field.pctBase:
                self._fields.append({
                    'name': f'pct_{fn}',
                    'caption': f'%{field.caption}',
                    'format': '{:.2%}',
                    'field-type': field.category
                })

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._delta) if self._delta is not None and not parent.isValid() else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._fields) if not parent.isValid() else 0

    def data(self, index: QModelIndex, role: int = ...):
        if self._delta:
            row = index.row()
            col = index.column()

            if role in {Qt.DisplayRole, Qt.EditRole}:
                value = self._delta[row, col]
                return self._fields[col]['format'].format(value) if value is not None else None

            if role == DeltaListModel.FieldTypeRole:
                return self._fields[col]['field-type']

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...):
        if self._delta:
            if role == Qt.DisplayRole:
                if orientation == Qt.Vertical:
                    return self._delta[section].name
                else:
                    return self._fields[section]['caption']
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignVCenter | Qt.AlignRight) if orientation == Qt.Horizontal else int(Qt.AlignCenter)

            if role == Qt.BackgroundRole and orientation == Qt.Horizontal:
                ft = self._fields[section]['field-type']
                if ft in FieldColors:
                    return QBrush(FieldColors[ft])

            if role == DeltaListModel.FieldTypeRole and orientation == Qt.Horizontal:
                return self._fields[section]['field-type']

        return None

    def startUpdate(self):
        self.beginResetModel()

    def endUpdate(self):
        self.endResetModel()


class DeltaFieldFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = None
        self._connection = None
        self._demographics: bool = True

    @property
    def deltaModel(self) -> DeltaListModel:
        return self.sourceModel()

    @property
    def plan(self):
        return self._plan

    def showDemographics(self, show: bool = True):
        if show != self._demographics:
            self._demographics = show
            self.invalidateFilter()

    def filterAcceptsColumn(self, source_column: int, source_parent: QModelIndex) -> bool:  # pylint: disable=unused-argument
        if source_parent.isValid():
            return True
        field_type = self.deltaModel._fields[source_column]['field-type']  # pylint: disable=protected-access
        return field_type == FieldCategory.Population or self._demographics


class GeoFieldsModel(QAbstractListModel):
    def __init__(self, plan: RdsPlan, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._data: list[RdsField] = list(plan.geoFields)
        self._data.insert(0, RdsField(plan.assignLayer, plan.geoIdField, plan.geoIdCaption))

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
    def __init__(self, plan: RdsPlan, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._data: list[RdsField] = list(plan.popFields)
        self._data.insert(0, RdsField(plan.popLayer, plan.popField,
                          DistrictColumns.POPULATION.comment))  # pylint: disable=no-member

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


class Metrics(IntEnum):
    Population = 0
    Deviation = 1
    Contiguity = 2
    Completeness = 3
    Compactness = 4


class RdsMetricsModel(QAbstractTableModel):
    MetricLabels = [
        DistrictColumns.POPULATION.comment,  # pylint: disable=no-member
        DistrictColumns.DEVIATION.comment,  # pylint: disable=no-member
        tr('Continguous'),
        tr('Complete'),
        tr('Compactness')
    ]
    # pylint: disable-next=no-member
    MetricLabels.extend(f"   {tr('Mean')} {s.comment}" for s in MetricsColumns.CompactnessScores())
    MetricLabels.extend(
        [
            tr('   Cut Edges'),
            tr('Splits')
        ]
    )

    SPLITS_OFFSET = len(MetricLabels)

    def __init__(self, metrics: RdsMetrics, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._metrics = None
        self.setMetrics(metrics)

    def setMetrics(self, value: RdsMetrics):
        self.beginResetModel()
        if self._metrics:
            self._metrics.metricsAboutToChange.disconnect(self.beginResetModel)
            self._metrics.metricsChanged.disconnect(self.endResetModel)
        self._metrics = value
        if self._metrics:
            self._metrics.metricsAboutToChange.connect(self.beginResetModel)
            self._metrics.metricsChanged.connect(self.endResetModel)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0

        c = RdsMetricsModel.SPLITS_OFFSET - 1
        if self._metrics and len(self._metrics.splits) > 0:
            c += 1 + len(self._metrics.splits)
        return c

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1 if not parent.isValid() else 0

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            if section >= RdsMetricsModel.SPLITS_OFFSET:
                split = self._metrics.splits[section-RdsMetricsModel.SPLITS_OFFSET]
                if split.geoField is None:
                    header = split.field
                else:
                    header = split.geoField.caption
                return f'   {textwrap.shorten(header, 20, placeholder="...")}'

            return RdsMetricsModel.MetricLabels[section]

        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if self._metrics is None or not index.isValid() or index.column() != 0:
            return None

        row = index.row()
        if role == Qt.DisplayRole:
            if row == Metrics.Population:
                result = f'{self._metrics.totalPopulation:,}'
            elif row == Metrics.Deviation:
                minDeviation, maxDeviation, _valid = self._metrics.deviation
                result = f'{maxDeviation:+.2%}, {minDeviation:+.2%}' \
                    if self._metrics.devationType == DeviationType.OverUnder \
                    else f'{maxDeviation-minDeviation:.2%}'
            elif row == Metrics.Contiguity:
                result = tr('Yes') if self._metrics.contiguous else tr('No')
            elif row == Metrics.Completeness:
                result = tr('Yes') if self._metrics.complete else tr('No')
            elif Metrics.Compactness < row <= Metrics.Compactness + len(MetricsColumns.CompactnessScores()):
                score = getattr(self._metrics, MetricsColumns.CompactnessScores()[row-Metrics.Compactness - 1])
                result = f'{score:.3f}' if score is not None else ''
            elif row == Metrics.Compactness + len(MetricsColumns.CompactnessScores()) + 1:
                result = f'{self._metrics.cutEdges:,}' if self._metrics.cutEdges else ''
            elif RdsMetricsModel.SPLITS_OFFSET <= row < RdsMetricsModel.SPLITS_OFFSET + len(self._metrics.splits):
                result = f'{len(self._metrics.splits[row-RdsMetricsModel.SPLITS_OFFSET]):,}'
            else:
                result = None
        elif role == Qt.FontRole:
            result = QFont()
            result.setBold(True)
        elif role == Qt.TextColorRole:
            if row == Metrics.Deviation:
                _min, _max, valid = self._metrics.deviation
                result = QColor(Qt.red) if not valid else QColor(Qt.green)
            elif row == Metrics.Contiguity:
                if not self._metrics.contiguous:
                    result = QColor(Qt.red)
                else:
                    result = QColor(Qt.green)
            elif row == Metrics.Completeness:
                if not self._metrics.complete:
                    result = QColor(Qt.red)
                else:
                    result = QColor(Qt.green)
            else:
                result = None
        elif role == Qt.ToolTipRole:
            if row == Metrics.Contiguity and not self._metrics.contiguous:
                result = tr('Plan contains non-contiguous districts\nDouble-click or press enter for details')
            elif row == Metrics.Completeness and not self._metrics.complete:
                result = tr('Plan contains unassigned geography\nDouble-click or press enter for details')
            elif RdsMetricsModel.SPLITS_OFFSET <= row < RdsMetricsModel.SPLITS_OFFSET + len(self._metrics.splits):
                result = tr('Double-click or press enter to see split details')
            else:
                result = None
        else:
            result = None

        return result

    def mimeTypes(self) -> List[str]:
        return ['text/csv', 'text/plain']

    def mimeData(self, indexes: Iterable[QModelIndex]) -> QMimeData:
        data = {self.headerData(idx.row(), Qt.Vertical, Qt.DisplayRole):
                self.data(idx, Qt.DisplayRole) or ''
                for idx in indexes}
        mime = QMimeData()
        mime.setData('text/csv', '\n'.join(','.join(r) for r in data.items()).encode())
        mime.setText('\n'.join('\t'.join(r) for r in data.items()))
        return mime


class RdsSplitsModel(QAbstractItemModel):
    def __init__(self, splits: RdsSplits, fields: Iterable[RdsField], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._splits = splits
        self._splits.splitUpdating.connect(self.beginResetModel)
        self._splits.splitUpdated.connect(self.endResetModel)
        self._data: pd.DataFrame = splits.data
        self._header = [self._splits.geoField.caption, tr("Districts"), tr('Population')]
        self._header.extend(f.caption for f in fields)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        if not parent.isValid():  # it's the root node
            return len(self._splits)

        if parent.column() > 0:
            return 0

        split: RdsSplitBase = parent.internalPointer()
        if isinstance(split, RdsSplitGeography):
            return len(split)

        return 0

    def columnCount(self, parent: QModelIndex = ...) -> int:
        if not parent.isValid():
            return max(2, self._splits.attrCount)

        split: Union[RdsSplitGeography, RdsSplitDistrict] = parent.internalPointer()
        if isinstance(split, RdsSplitGeography):
            return self._splits.attrCount

        return 0

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags

        return super().flags(index)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return QVariant()

        item: RdsSplitBase = index.internalPointer()
        col = index.column()
        if isinstance(item, RdsSplitGeography):
            if col >= 2:
                return QVariant()
        else:
            if col == 0:
                return QVariant()
            col -= 1

        if role == Qt.DisplayRole:
            value = item.attributes[col]
            if isinstance(value, (int, np.integer)):
                value = f'{value:,}'
            elif isinstance(value, (float, np.floating)):
                value = f'{value:,.2f}'
            return value

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> Any:
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._header[section] if section < len(self._header) else ""

        return QVariant()

    def index(self, row: int, column: int, parent: QModelIndex = ...) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            return self.createIndex(row, column, self._splits[row])

        parentItem: RdsSplitBase = parent.internalPointer()
        if isinstance(parentItem, RdsSplitDistrict):  # shouldn't happen
            return QModelIndex()

        return self.createIndex(row, column, parentItem[row])

    def parent(self, index: QModelIndex = ...) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        split: RdsSplitBase = index.internalPointer()
        if isinstance(split, RdsSplitDistrict):
            return self.createIndex(self._splits.index(split.parent), 0, split.parent)

        return QModelIndex()
