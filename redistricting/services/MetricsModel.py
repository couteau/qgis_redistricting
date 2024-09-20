import textwrap
from enum import IntEnum
from typing import (
    Any,
    Iterable,
    List,
    Optional
)

from qgis.PyQt.QtCore import (
    QAbstractTableModel,
    QMimeData,
    QModelIndex,
    QObject,
    Qt
)
from qgis.PyQt.QtGui import (
    QColor,
    QFont
)

from ..models import (
    DeviationType,
    DistrictColumns,
    MetricsColumns,
    RdsPlanMetrics
)
from ..utils import tr


class Metrics(IntEnum):
    Population = 0
    Deviation = 1
    Contiguity = 2
    Completeness = 3
    CompactnessSection = 4


class RdsPlanMetricsModel(QAbstractTableModel):
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

    def __init__(self, metrics: RdsPlanMetrics, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._metrics = None
        self.setMetrics(metrics)

    def setMetrics(self, value: RdsPlanMetrics):
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

        c = RdsPlanMetricsModel.SPLITS_OFFSET - 1
        if self._metrics and len(self._metrics.splits) > 0:
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
            if row == Metrics.Population:
                result = f'{self._metrics.totalPopulation:,}'
            elif row == Metrics.Deviation:
                minDeviation, maxDeviation, _valid = self._metrics.deviation
                result = f'{maxDeviation:+.2%}, {minDeviation:+.2%}' if self._metrics.devationType == DeviationType.OverUnder else f'{maxDeviation-minDeviation:.2%}'
            elif row == Metrics.Contiguity:
                result = tr('Yes') if self._metrics.contiguous else tr('No')
            elif row == Metrics.Completeness:
                result = tr('Yes') if self._metrics.complete else tr('No')
            elif Metrics.CompactnessSection < row <= Metrics.CompactnessSection + len(MetricsColumns.CompactnessScores()):
                score = getattr(self._metrics, MetricsColumns.CompactnessScores()[row-Metrics.CompactnessSection - 1])
                result = f'{score:.3f}' if score is not None else ''
            elif row == Metrics.CompactnessSection + len(MetricsColumns.CompactnessScores()) + 1:
                result = f'{self._metrics.cutEdges:,}' if self._metrics.cutEdges else ''
            elif RdsPlanMetricsModel.SPLITS_OFFSET <= row < RdsPlanMetricsModel.SPLITS_OFFSET + len(self._metrics.splits):
                result = f'{len(self._metrics.splits[row-RdsPlanMetricsModel.SPLITS_OFFSET]):,}'
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
            elif RdsPlanMetricsModel.SPLITS_OFFSET <= row < RdsPlanMetricsModel.SPLITS_OFFSET + len(self._metrics.splits):
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
