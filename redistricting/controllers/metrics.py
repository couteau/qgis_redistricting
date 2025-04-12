# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Controller for Metrics Table functions

        begin                : 2024-09-20
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
import csv
import io
from typing import Optional

from qgis.core import (
    QgsApplication,
    QgsProject
)
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import (
    QModelIndex,
    QObject,
    Qt
)
from qgis.PyQt.QtGui import (
    QIcon,
    QKeySequence
)
from qgis.PyQt.QtWidgets import QToolBar

from ..gui import (
    DockPlanMetrics,
    RdsMetricGuiHandler,
    TableViewKeyEventFilter,
    get_metric_handler
)
from ..models import (
    RdsMetric,
    RdsMetricsModel,
    RdsPlan
)
from ..services import (
    ActionRegistry,
    DistrictUpdater,
    PlanManager
)
from .base import DockWidgetController


class MetricsController(DockWidgetController):
    def __init__(self, iface: QgisInterface, project: QgsProject, planManager: PlanManager, toolbar: QToolBar, updateService: DistrictUpdater, parent: Optional[QObject] = None):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.updateService = updateService

        self.dockwidget: DockPlanMetrics
        self.metricsModel = RdsMetricsModel(None)

        self.actions = ActionRegistry()

        self.actionCopyMetrics = self.actions.createAction(
            name="actionCopyMetrics",
            icon=QgsApplication.getThemeIcon('/mActionEditCopy.svg'),
            text=self.tr("Copy Metrics"),
            tooltip=self.tr("Copy metrics to clipboard"),
            callback=self.copyMetrics,
            parent=self.iface.mainWindow()
        )
        self.actionCopySelectedMetrics = self.actions.createAction(
            name="actionCopyselectedMetrics",
            icon=QgsApplication.getThemeIcon('/mActionEditCopy.svg'),
            text=self.tr("Copy Metrics"),
            tooltip=self.tr("Copy selected metrics to clipboard"),
            callback=self.copySelection,
            shortcut=QKeySequence.StandardKey.Copy,
            parent=self.iface.mainWindow()
        )

        self.handler_cache: dict[type[RdsMetric], RdsMetricGuiHandler] = {}

    def createDockWidget(self):
        dockwidget = DockPlanMetrics(self.iface.mainWindow())
        dockwidget.btnCopy.setDefaultAction(self.actionCopyMetrics)
        dockwidget.tblPlanMetrics.setModel(self.metricsModel)
        dockwidget.tblPlanMetrics.installEventFilter(TableViewKeyEventFilter(dockwidget))
        dockwidget.tblPlanMetrics.activated.connect(self.showMetricsDetail)
        return dockwidget

    def createToggleAction(self):
        action = super().createToggleAction()
        if action is not None:
            action.setIcon(QIcon(':/plugins/redistricting/planmetrics.svg'))
            action.setText('Plan metrics')
            action.setToolTip('Show/hide plan metrics')

        return action

    def load(self):
        super().load()
        self.planManager.activePlanChanged.connect(self.planChanged)
        self.planManager.planAdded.connect(self.planAdded)
        self.planManager.planRemoved.connect(self.planRemoved)
        self.updateService.updateStarted.connect(self.showOverlay)
        self.updateService.updateComplete.connect(self.hideOverlay)
        self.updateService.updateTerminated.connect(self.hideOverlay)

    def unload(self):
        self.updateService.updateStarted.disconnect(self.showOverlay)
        self.updateService.updateComplete.disconnect(self.hideOverlay)
        self.updateService.updateTerminated.disconnect(self.hideOverlay)
        self.planManager.planRemoved.disconnect(self.planRemoved)
        self.planManager.planAdded.disconnect(self.planAdded)
        self.planManager.activePlanChanged.disconnect(self.planChanged)
        super().unload()

    def planChanged(self, plan: RdsPlan):
        self.dockwidget.setWaiting(False)
        self.metricsModel.setPlan(plan)
        self.dockwidget.plan = plan
        if plan is None:
            handlers = list(self.handler_cache.values())
            for handler in handlers:
                handler.deactivate()

            self.handler_cache = {}
        else:
            for handler in self.handler_cache.values():
                handler.update(plan)

        if self.updateService.planIsUpdating(plan):
            self.dockwidget.setWaiting(True)

    def planAdded(self, plan: RdsPlan):
        plan.metricsChanged.connect(self.updateMetricsDetail)

    def planRemoved(self, plan: RdsPlan):
        plan.metricsChanged.disconnect(self.updateMetricsDetail)

    def showOverlay(self, plan: RdsPlan):
        if plan == self.activePlan:
            self.dockwidget.setWaiting(True)

    def hideOverlay(self, plan: RdsPlan):
        if plan == self.activePlan:
            self.dockwidget.setWaiting(False)

    def copyMetrics(self):
        indexes = (self.metricsModel.createIndex(d, 0) for d in range(self.metricsModel.rowCount()))
        QgsApplication.instance().clipboard().setMimeData(self.metricsModel.mimeData(indexes))

    def copySelection(self):
        selection = self.dockwidget.tblPlanMetrics.selectedIndexes()
        if selection:
            selection.sort(key=lambda idx: idx.row())
            table = []
            for idx in selection:
                table.append([self.metricsModel.headerData(
                    idx.row(), Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole), idx.data()])
            stream = io.StringIO()
            csv.writer(stream, delimiter='\t').writerows(table)
            QgsApplication.instance().clipboard().setText(stream.getvalue())

    def showMetricsDetail(self, index: QModelIndex):
        metric = self.metricsModel.metric(index)

        if type(metric) in self.handler_cache:
            handler = self.handler_cache[type(metric)]
        else:
            handler = get_metric_handler(metric)
            handler.deactivated.connect(self.handlerDeactivated)
            if handler is None:
                return
            self.handler_cache[type(metric)] = handler

        idx = self.metricsModel.metricKey(index.row())
        handler.show(self.activePlan, metric, idx)

    def updateMetricsDetail(self):
        if self.sender() == self.activePlan:
            for metric in self.activePlan.metrics.metrics:
                if type(metric) in self.handler_cache:
                    self.handler_cache[type(metric)].update(self.activePlan, metric)

    def handlerDeactivated(self):
        handler: RdsMetricGuiHandler = self.sender()

        handler.deactivated.disconnect(self.handlerDeactivated)

        if handler in self.handler_cache.values():
            if handler.metric is not None:
                k = type(handler.metric)
            else:
                for k, v in self.handler_cache.items():
                    if v is handler:
                        break
                else:
                    return

            del self.handler_cache[k]
