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
from qgis.PyQt.QtGui import (
    QBrush,
    QIcon,
    QPainter,
    QPixmap
)

from ..models import (
    RdsDistrict,
    RdsPlan
)
from ..utils import tr
from .PlanColors import getColorForDistrict


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
