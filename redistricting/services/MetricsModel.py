import textwrap
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

from ..models import RdsPlanMetrics
from ..utils import tr


class RdsPlanMetricsModel(QAbstractTableModel):
    MetricLabels = [
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

    def __init__(self, metrics: RdsPlanMetrics, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._metrics = None
        self.setMetrics(metrics)

    def setMetrics(self, value: RdsPlanMetrics):
        self.beginResetModel()
        if self._metrics:
            self._metrics.metricsAboutToChange.disconnect(self.beginResetModel)
            self._metrics.metricsChanged.disconnect(self.endResetModel)
            for s in self._metrics.splits.values():
                s.splitUpdating.disconnect(self.beginResetModel)
                s.splitUpdated.disconnect(self.endResetModel)
        self._metrics = value
        if self._metrics:
            self._metrics.metricsAboutToChange.connect(self.beginResetModel)
            self._metrics.metricsChanged.connect(self.endResetModel)
            for s in self._metrics.splits.values():
                s.splitUpdating.connect(self.beginResetModel)
                s.splitUpdated.connect(self.endResetModel)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0

        c = RdsPlanMetricsModel.SPLITS_OFFSET - 1
        if self._metrics:
            c += 1 + len(self._metrics.splits)
        return c

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1 if not parent.isValid() else 0

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            if section >= RdsPlanMetricsModel.SPLITS_OFFSET:
                split = self._metrics.splits[section-RdsPlanMetricsModel.SPLITS_OFFSET]
                if split.geoField is None:
                    header = split.field
                else:
                    header = split.geoField.caption
                return f'   {textwrap.shorten(header, 20, placeholder="...")}'

            return RdsPlanMetricsModel.MetricLabels[section]

        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if self._metrics is None or not index.isValid() or index.column() != 0:
            return None

        row = index.row()
        if role == Qt.DisplayRole:
            if row == 0:
                result = f'{self._metrics.totalPopulation:,}'
            elif row == 1:
                result = tr('Yes') if self._metrics.contiguous else tr('No')
            elif row == 3:
                avgPP = self._metrics.polsbypopper
                result = f'{avgPP:.3f}' if avgPP is not None else ''
            elif row == 4:
                avgReock = self._metrics.reock
                result = f'{avgReock:.3f}' if avgReock is not None else ''
            elif row == 5:
                avgCH = self._metrics.convexhull
                result = f'{avgCH:.3f}' if avgCH is not None else ''
            elif row == 6:
                result = f'{self._metrics.cutEdges:,}' if self._metrics.cutEdges else ''
            elif row in (2, RdsPlanMetricsModel.SPLITS_OFFSET - 1):
                result = None
            elif row <= RdsPlanMetricsModel.SPLITS_OFFSET + len(self._metrics.splits):
                result = f'{len(self._metrics.splits[row-RdsPlanMetricsModel.SPLITS_OFFSET]):,}'
            else:
                result = None
        elif role == Qt.FontRole:
            result = QFont()
            result.setBold(True)
        elif role == Qt.TextColorRole:
            if row == 1:
                if not self._metrics.contiguous:
                    result = QColor(Qt.red)
                else:
                    result = QColor(Qt.green)
            else:
                result = None
        else:
            result = None

        return result
