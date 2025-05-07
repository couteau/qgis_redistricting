"""QGIS Redistricting Plugin - gui hanlder base class for metrics

        begin                : 2025-01-20
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
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

from typing import Any, Optional, Union

from qgis.PyQt.QtCore import QObject, pyqtSignal

from ..models import RdsMetric, RdsPlan


class RdsMetricGuiHandler(QObject):
    deactivated = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.plan: RdsPlan = None
        self.metric: RdsMetric = None
        self.idx: Any = None

    def show(self, plan: RdsPlan, metric: RdsMetric, idx: Any = None):
        self.plan = plan
        self.metric = metric
        self.idx = idx

    def update(self, plan: RdsPlan, metric: RdsMetric = None, idx: Any = None):
        self.plan = plan
        if metric is None:
            if self.metric is not None and self.metric.name() in plan.metrics.metrics.keys():
                metric = plan.metrics.metrics[self.metric.name()]
            else:
                # if the new plan doesn't have the metric assocated with this handler, deactivate the handler
                self.deactivate()
                return

        self.metric = metric
        self.idx = idx or self.idx

    def deactivate(self):
        self.deactivated.emit()


metrics_handlers: dict[type[RdsMetric], RdsMetricGuiHandler] = {}


def register_metric_handler(metric_class: type[RdsMetric], handler: RdsMetricGuiHandler):
    metrics_handlers[metric_class] = handler


def get_metric_handler(metric: Union[RdsMetric, type[RdsMetric]]) -> RdsMetricGuiHandler:
    if isinstance(metric, RdsMetric):
        metric = type(metric)

    handler = metrics_handlers.get(metric)
    if issubclass(handler, RdsMetricGuiHandler):
        handler = handler()

    return handler
