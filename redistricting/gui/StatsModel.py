from typing import (
    Any,
    Optional
)

from qgis.PyQt.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt
)
from qgis.PyQt.QtGui import (
    QColor,
    QFont
)

from ..models import RdsPlanStats
from ..utils import tr


class StatsModel(QAbstractTableModel):
    StatLabels = [
        tr('Population'),
        tr('Continguous'),
        tr('Compactness'),
        tr('   Avg. Polsby-Popper'),
        tr('   Avg. Reock'),
        tr('   Avg. Convex-Hull'),
        tr('   Cut Edges'),
        tr('Splits')
    ]
    SPLITS_OFFSET = 8

    def __init__(self, stats: RdsPlanStats, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._stats = None
        self.setStats(stats)

    def setStats(self, value: RdsPlanStats):
        self.beginResetModel()
        if self._stats:
            self._stats.statsUpdating.disconnect(self.beginResetModel)
            self._stats.statsUpdated.disconnect(self.endResetModel)
            for s in self._stats.splits.values():
                s.splitUpdating.disconnect(self.beginResetModel)
                s.splitUpdated.disconnect(self.endResetModel)
        self._stats = value
        if self._stats:
            self._stats.statsUpdating.connect(self.beginResetModel)
            self._stats.statsUpdated.connect(self.endResetModel)
            for s in self._stats.splits.values():
                s.splitUpdating.connect(self.beginResetModel)
                s.splitUpdated.connect(self.endResetModel)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0

        c = StatsModel.SPLITS_OFFSET - 1
        if self._stats:
            c += 1 + len(self._stats.splits)
        return c

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1 if not parent.isValid() else 0

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return StatsModel.StatLabels[section] \
                if section < StatsModel.SPLITS_OFFSET \
                else '   ' + self._stats.splits.headings[section-StatsModel.SPLITS_OFFSET]

        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if self._stats is None or not index.isValid() or index.column() != 0:
            return None

        row = index.row()
        if role == Qt.DisplayRole:
            if row == 0:
                result = f'{self._stats.totalPopulation:,}'
            elif row == 1:
                result = tr('Yes') if self._stats.contiguous else tr('No')
            elif row == 3:
                avgPP = self._stats.avgPolsbyPopper
                result = f'{avgPP:.3f}' if avgPP is not None else ''
            elif row == 4:
                avgReock = self._stats.avgReock
                result = f'{avgReock:.3f}' if avgReock is not None else ''
            elif row == 5:
                avgCH = self._stats.avgConvexHull
                result = f'{avgCH:.3f}' if avgCH is not None else ''
            elif row == 6:
                result = f'{self._stats.cutEdges:,}' if self._stats.cutEdges else ''
            elif row in (2, StatsModel.SPLITS_OFFSET - 1):
                result = None
            elif row <= StatsModel.SPLITS_OFFSET + len(self._stats.splits):
                result = f'{len(self._stats.splits[row-StatsModel.SPLITS_OFFSET]):,}'
            else:
                result = None
        elif role == Qt.FontRole:
            result = QFont()
            result.setBold(True)
        elif role == Qt.TextColorRole:
            if row == 1:
                if not self._stats.contiguous:
                    result = QColor(Qt.red)
                else:
                    result = QColor(Qt.green)
            else:
                result = None
        else:
            result = None

        return result
