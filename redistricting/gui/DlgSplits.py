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
from numbers import Number
from typing import (
    Iterable,
    Optional,
    Union
)

from qgis.PyQt.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    Qt,
    QVariant
)
from qgis.PyQt.QtGui import (
    QStandardItem,
    QStandardItemModel
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QWidget
)

from ..core import (
    BasePopulation,
    Field,
    RedistrictingPlan
)
from ..core.utils import (
    makeFieldName,
    tr
)
from .ui.DlgSplits import Ui_dlgSplits


# TODO: Using this wrapper model is hanging QGIS for some reason I can't resolve
class SplitsModel(QAbstractItemModel):
    _plan: RedistrictingPlan = None

    def __init__(self, plan: RedistrictingPlan = None, geoField: Field = None, parent: QObject = None):
        super().__init__(parent)
        self._keys = []
        self._headings = []
        self._splits = {}
        self._field = geoField
        self.plan = plan

    def __del__(self):
        self.plan = None

    @ property
    def plan(self) -> RedistrictingPlan:
        return self._plan

    @ plan.setter
    def plan(self, value: RedistrictingPlan):
        if value != self._plan:
            self.beginResetModel()

            if self._plan is not None:
                self._plan.stats.statsChanged.disconnect(self.statsChanged)
                self._plan.planChanged.disconnect(self.planChanged)

            self._plan = value
            if self._plan is not None:
                self._plan.stats.statsChanged.connect(self.statsChanged)
                self._plan.planChanged.connect(self.planChanged)
            
            self.updateSplits()
            self.updateColumnKeys()
            self.endResetModel()

    @property
    def field(self):
        return self._field
    
    @field.setter
    def field(self, value: Field):
        if value != self._field:
            self.beginResetModel()
            self._field = value
            self.updateSplits()
            self.updateColumnKeys()
            self.endResetModel()

    def updateSplits(self):
        if self._plan and self._field:
            if self._field not in self._plan.dataFields:
                raise ValueError(
                    f"Cannot show splits for {self._field.fieldName}. Field {self._field.field} not in plan {self._plan.name}")
            if not self._field in self._plan.stats.splits:
                self._splits = {}
            else:
                self._splits = self._plan.stats.splits[self._field]

    def updateColumnKeys(self):
        if self._plan is None or self._field is None:
            self._headings = []
            self._subheadings = []
            self._keys = []
            self._subkeys = []
            return
        
        self._keys = [
            self._field.fieldName,
            "districts"
        ]

        self._subkeys = [
            "district",
            self._plan.popField
        ]

        self._headings = [
            self._field.caption,
            tr('Districts'),
            tr('Population')
        ]

        if self._plan.vapField:
            self._subkeys.append(self._plan.vapField)
            self._headings.append(tr('VAP'))

        if self._plan.cvapField:
            self._subkeys.append(self._plan.cvapField)
            self._headings.append(tr('CVAP'))
        for field in self._plan.dataFields:
            fn = makeFieldName(field)
            if field.sum:
                self._subkeys.append(fn)
                self._headings.append(field.caption)
            if field.pctbase:
                self._subkeys.append(f'pct_{fn}')
                self._headings.append(f'%{field.caption}')

    def planChanged(self, plan, prop, value, oldValue):  # pylint: disable=unused-argument
        if prop in ('districts', 'data-fields', 'pop-field', 'vap-field', 'cvap-field'):
            self.beginResetModel()
            self.updateColumnKeys()
            self.endResetModel()

    def statsChanged(self):
        self.beginResetModel()
        self.updateSplits()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
       if not parent.isValid():
            return len(self._splits)
       else:
            return len(self._splits[parent.row()]['districts'])
       
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headings)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):            
        if role in (Qt.DisplayRole, Qt.EditRole):
            row = index.row()
            column = index.column()

            if not index.parent().isValid():
                if column >= len(self._keys):
                    return QVariant()
                
                key = self._keys[column]
                value = self._splits[row][key]
                if key == "districts" and isinstance(value, dict):
                    value = ','.join(d for d in value.keys())
            else:
                if column == 0:
                    return ""
                
                key = self._subkeys[column-1]

                if key == 'district':
                    value = self._splits[index.parent().row()]['districts'].keys()[row]
                else:
                    split_detail: dict = self._splits[index.parent().row()]['districts'].values()[row]
                
                    if key[:3] == 'pct_':
                        k = key[5:]
                        f = self.plan.dataFields[k]
                        v = split_detail.values()[k]
                        if f.pctbase == BasePopulation.TOTALPOP:
                            base = split_detail[self.plan.popField]
                        elif f.pctbase == BasePopulation.VAP and self.plan.vapField:
                            base = split_detail[self.plan.vapField]
                        elif f.pctbase == BasePopulation.CVAP and self.plan.cvapField:
                            base = split_detail[self.plan.cvapField]
                        else:
                            return "N/A"
                        if base != 0:
                            value = v / base
                        else:
                            value = 0
                        value = f'{value:.2%}'
                    elif isinstance(value, Number):
                        value = f'{split_detail[key]:,}'

            if value is None:
                return QVariant()
            return value

        return QVariant()

    def headerData(self, section, orientation: Qt.Orientation, role):
        if (role == Qt.DisplayRole and orientation == Qt.Horizontal):
            if section < len(self._headings):
                return self._headings[section]

        return QVariant()
    
    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        if not parent.isValid():
            return True
        
        if parent.internalPointer() is not None or parent.column() != 0:
            return False
        
        return isinstance(self._splits[parent.row()]['districts'], Iterable)
    
    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        
        item = index.internalPointer()
        if item is None:
            return QModelIndex()
        else:
            return self.createIndex(item, 0)
    
    def index(self, row: int, column: int, parent: QModelIndex) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        
        if not parent.isValid():
            idx = self.createIndex(row, column)
        else:
            idx = self.createIndex(row, column, parent.row())
        
        return idx

class DlgSplitDetail(Ui_dlgSplits, QDialog):
    def __init__(self, plan: RedistrictingPlan, geoField: Field, parent: Optional[QWidget] = None, flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.Dialog):
        super().__init__(parent, flags)
        self.setupUi(self)

        self._model = None
        self._plan: RedistrictingPlan = None
        self._field: Field = None

        self.plan = plan
        self.geoField = geoField

    def makeModel(self):
        if self._plan is None or self._field is None:
            model = QStandardItemModel(0, 0, self)
            return model
        
        
        headings = [
            self._field.caption,
            tr('Districts')
        ]
        h = True
        
        model = QStandardItemModel()
        
        root = model.invisibleRootItem()
        for s in self._plan.stats.splits[self._field]:
            split = QStandardItem(s[self._field.fieldName])
            if isinstance(s["districts"], dict):
                districts = ','.join(d for d in s["districts"].keys())
            else:
                districts = s["districts"]
            root.appendRow([split, QStandardItem(districts)])
            if isinstance(s["districts"], dict):
                if h:
                    headings.append(tr('Population'))
                for district, pop in s["districts"].items():
                    children = [QStandardItem(""), QStandardItem(district), QStandardItem(f"{pop[self._plan.popField]:,}")]

                    if self._plan.vapField:
                        children.append(QStandardItem(f"{pop[self._plan.vapField]:,}"))
                        if h:
                            headings.append(tr('VAP'))
                    if self._plan.cvapField:
                        children.append(QStandardItem(f"{pop[self._plan.cvapField]:,}"))
                        if h:
                            headings.append(tr('CVAP'))
                    for field in self._plan.dataFields:
                        v = pop[field.fieldName]
                        if field.sum:
                            children.append(QStandardItem(f"{v:,}"))
                            if h:
                                headings.append(field.caption)
                        if field.pctbase != BasePopulation.NOPCT:
                            if field.pctbase == BasePopulation.TOTALPOP:
                                base = pop[self.plan.popField]
                            elif field.pctbase == BasePopulation.VAP and self.plan.vapField:
                                base = pop[self.plan.vapField]
                            elif field.pctbase == BasePopulation.CVAP and self.plan.cvapField:
                                base = pop[self.plan.cvapField]
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
                    split.appendRow(children)

        model.setHorizontalHeaderLabels(headings)
        return model
        
    @property
    def plan(self) -> RedistrictingPlan:
        return self._plan
    
    @plan.setter
    def plan(self, value: RedistrictingPlan):
        self._plan = value
        #self._model =  SplitsModel(self._plan, self._field)
        self._model = self.makeModel()
        self.tvSplits.setModel(self._model)

    @property
    def geoField(self) -> Field:
        return self._field
    
    @geoField.setter
    def geoField(self, value: Field):
        self._field = value
        if self._field:
            self.setWindowTitle(f"{self._field.caption} {tr('Splits')}")

        #self._model =  SplitsModel(self._plan, self._field)
        self._model = self.makeModel()
        self.tvSplits.setModel(self._model)
