from qgis.PyQt.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSize,
    Qt
)
from qgis.PyQt.QtGui import (
    QColor,
    QFont
)

from ..utils import tr
from .PlanManager import PlanManager


class PlanListModel(QAbstractTableModel):
    def __init__(self, planList: PlanManager, parent=None):
        super().__init__(parent)
        self.planList = planList
        self.planList.activePlanChanged.connect(self.planListUpdated)
        self.planList.planAdded.connect(self.planListUpdated)
        self.planList.planRemoved.connect(self.planListUpdated)

        self.header = [
            tr('Plan'),
            tr('Districts'),
            tr('Description')
        ]

    def rowCount(self, parent: QModelIndex = ...) -> int:  # pylint: disable=unused-argument
        return len(self.planList)

    def columnCount(self, parent: QModelIndex = ...) -> int:  # pylint: disable=unused-argument,no-self-use
        return 3

    def headerData(self, section, orientation: Qt.Orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.header[section]
            if role == Qt.SizeHintRole:
                if section in (0, 2):
                    return QSize(150, 30)

        return None

    def data(self, index, role):
        if role == Qt.DisplayRole:
            plan = self.planList[index.row()]
            if index.column() == 0:
                v = plan.name
            elif index.column() == 1:
                v = f"{plan.numDistricts:,}"
            elif index.column() == 2:
                v = plan.description
            else:
                v = None
            return v
        elif role == Qt.TextAlignmentRole and index.column() == 1:
            return int(Qt.AlignRight | Qt.AlignCenter)
        elif role == Qt.FontRole:
            if index.row() == self.activePlanIndex().row():
                f = QFont()
                f.setBold(True)
                return f
        elif role == Qt.TextColorRole:
            if index.row() == self.activePlanIndex().row():
                return QColor(Qt.blue)

    @property
    def activePlan(self):
        return self.planList.activePlan

    def planIndex(self, plan):
        try:
            row = self.planList.index(plan)
            return self.createIndex(row, 0)
        except:  # pylint: disable=bare-except
            pass

        return QModelIndex()

    def activePlanIndex(self):
        if self.activePlan is None:
            return QModelIndex()

        return self.planIndex(self.activePlan)

    def plan(self, index: QModelIndex):
        if 0 <= index.row() < len(self.planList):
            return self.planList[index.row()]

        return None

    def planListUpdated(self):
        self.beginResetModel()
        self.endResetModel()

    def updatePlan(self, plan):
        idx1 = self.planIndex(plan)
        idx2 = self.createIndex(idx1.row(), self.columnCount() - 1)
        self.dataChanged.emit(idx1, idx2)
