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
from typing import (
    Any,
    Optional,
    Union
)

from qgis.core import (
    QgsApplication,
    QgsAttributeTableConfig,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeatureRequest,
    QgsProject,
    QgsVectorLayerCache
)
from qgis.gui import (
    QgisInterface,
    QgsAttributeTableFilterModel,
    QgsAttributeTableModel
)
from qgis.PyQt.QtCore import (
    QLocale,
    QModelIndex,
    QObject,
    Qt
)
from qgis.PyQt.QtGui import (
    QIcon,
    QKeySequence
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QStyledItemDelegate,
    QTableView,
    QToolBar,
    QVBoxLayout
)

from ..gui import (
    DlgSplitDetail,
    DockPlanMetrics,
    TableViewKeyEventFilter
)
from ..models import (
    DistrictColumns,
    RdsGeoField,
    RdsMetricsModel,
    RdsPlan,
    RdsSplitsModel
)
from ..services import (
    ActionRegistry,
    DistrictUpdater,
    PlanManager
)
from ..utils import tr
from .base import DockWidgetController


class RdsNullsAsBlanksDelegate(QStyledItemDelegate):
    def displayText(self, value: Any, locale: QLocale) -> str:
        if value == 'NULL':
            return super().displayText("", locale)

        return super().displayText(value, locale)


class MetricsController(DockWidgetController):
    def __init__(self, iface: QgisInterface, project: QgsProject, planManager: PlanManager, toolbar: QToolBar, updateService: DistrictUpdater, parent: Optional[QObject] = None):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.updateService = updateService

        self.dockwidget: DockPlanMetrics

        self.metricsModel = RdsMetricsModel(None)
        self.dlgSplits: DlgSplitDetail = None
        self.dlgSplitDistricts: QDialog = None
        self.splitDistrictsModel: QgsAttributeTableFilterModel = None
        self.dlgUnassignedGeography: QDialog = None
        self.unassignedGeographyModel: QgsAttributeTableFilterModel = None

        self.actions = ActionRegistry()
        self.actionShowSplitsDialog = self.actions.createAction(
            name="actionShowSplitsDialog",
            icon=QgsApplication.getThemeIcon('/mActionSplitFeatures.svg'),
            text=self.tr("Split detail"),
            callback=self.showSplits
        )
        self.actionShowSplitsDialog.setEnabled(False)
        self.actionShowSplitDistrictsDialog = self.actions.createAction(
            name="actionShowSplitDistrictsDialog",
            icon=QgsApplication.getThemeIcon('/mActionSplitParts.svg'),
            text=self.tr("Split districts"),
            callback=self.showSplitDistricts
        )
        self.actionShowSplitDistrictsDialog.setEnabled(False)
        self.actionShowUnassignedGeographyDialog = self.actions.createAction(
            name="actionShowUnassignedGeographyDialog",
            icon=QgsApplication.getThemeIcon('/mActionSplitParts.svg'),
            text=self.tr("Unassigned geography"),
            callback=self.showUnassignedGeography
        )
        self.actionShowUnassignedGeographyDialog.setEnabled(False)

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
            shortcut=QKeySequence.Copy,
            parent=self.iface.mainWindow()
        )

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
        if plan is not None:
            self.metricsModel.setMetrics(plan.metrics)
        else:
            self.metricsModel.setMetrics(None)
        self.dockwidget.plan = plan
        if self.dlgSplits:
            self.dlgSplits.close()
            self.dlgSplits = None
        self.actionShowSplitsDialog.setEnabled(plan is not None)
        self.actionShowSplitDistrictsDialog.setEnabled(plan is not None)
        self.actionShowUnassignedGeographyDialog.setEnabled(plan is not None)
        if self.dlgUnassignedGeography is not None:
            self.dlgUnassignedGeography.close()
            self.dlgUnassignedGeography.destroy(True, True)
            self.dlgUnassignedGeography = None
        if self.dlgSplitDistricts is not None:
            self.dlgSplitDistricts.close()
            self.dlgSplitDistricts.destroy(True, True)
            self.dlgSplitDistricts = None
        if self.updateService.planIsUpdating(plan):
            self.dockwidget.setWaiting(True)

    def planAdded(self, plan: RdsPlan):
        plan.metricsChanged.connect(self.updateMetricsDialogs)

    def planRemoved(self, plan: RdsPlan):
        plan.metricsChanged.disconnect(self.updateMetricsDialogs)

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
                    idx.row(), Qt.Vertical, Qt.DisplayRole), idx.data()])
            stream = io.StringIO()
            csv.writer(stream, delimiter='\t').writerows(table)
            QgsApplication.instance().clipboard().setText(stream.getvalue())

    def deleteDialog(self, dlg: QObject):
        if dlg.objectName() == 'dlgSplits':
            self.dlgSplits = None
        elif dlg.objectName() == 'dlgSplitDistricts':
            self.dlgSplitDistricts = None
        elif dlg.objectName() == 'dlgUnassignedGeography':
            self.dlgUnassignedGeography = None

    def showMetricsDetail(self, index: QModelIndex):
        row = index.row()
        if row == 2:
            if not self.actionShowSplitDistrictsDialog.isEnabled():
                return
            self.actionShowSplitDistrictsDialog.trigger()
        elif row == 3:
            if not self.actionShowUnassignedGeographyDialog.isEnabled():
                return
            self.actionShowUnassignedGeographyDialog.trigger()
        elif row >= self.metricsModel.SPLITS_OFFSET:
            if not self.actionShowSplitsDialog.isEnabled():
                return
            field = self.planManager.activePlan.geoFields[row-self.metricsModel.SPLITS_OFFSET]
            self.actionShowSplitsDialog.setData(field)
            self.actionShowSplitsDialog.trigger()

    def showSplits(self, field: Optional[RdsGeoField] = None):
        if not isinstance(field, RdsGeoField):
            field = self.sender().data()

        if field is None:
            return

        if self.dlgSplits is None:
            self.dlgSplits = DlgSplitDetail(self.planManager.activePlan, self.iface.mainWindow())
            self.dlgSplits.setAttribute(Qt.WA_DeleteOnClose, True)
            self.dlgSplits.destroyed.connect(self.deleteDialog)
            self.dlgSplits.geographyChanged.connect(self.updateSplitsDialog)

        self.updateSplitsDialog(field)

        self.dlgSplits.show()

    def updateSplitsDialog(self, field: Union[RdsGeoField, int]):
        if isinstance(field, int):
            field: RdsGeoField = self.activePlan.geoFields[field]
        self.dlgSplits.setWindowTitle(f"{field.caption} {tr('Splits')}")
        model = RdsSplitsModel(
            self.activePlan.metrics.splits[field.field],
            (*self.activePlan.popFields, *self.activePlan.dataFields)
        )
        self.dlgSplits.setModel(model)
        self.dlgSplits.cmbGeography.setCurrentText(field.caption)

    def zoomToSplitDistrict(self, index: QModelIndex):
        filter_id = self.splitDistrictsModel.rowToId(index)
        fid = self.splitDistrictsModel.layer().getFeature(filter_id)[0]
        self.iface.mapCanvas().zoomToFeatureIds(self.activePlan.distLayer, [fid])

    def createSplitDistrictsModel(self):
        ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(self.activePlan.distLayer))
        expr = QgsExpression('num_geometries(@geometry) > 1')
        req = QgsFeatureRequest(expr, ctx)
        req.setSubsetOfAttributes(
            ["fid", self.activePlan.distField, DistrictColumns.NAME, DistrictColumns.POPULATION, 'description'],
            self.activePlan.distLayer.fields())
        layer = self.activePlan.distLayer.materialize(req)
        layer.setParent(self.dlgSplitDistricts)

        # pylint: disable=no-member
        layer.setFieldAlias(1, DistrictColumns.DISTRICT.comment)
        layer.setFieldAlias(2, DistrictColumns.NAME.comment)
        layer.setFieldAlias(3, DistrictColumns.POPULATION.comment)
        layer.setFieldAlias(4, tr("Description"))
        # pylint: enable=no-member

        layerCache = QgsVectorLayerCache(layer, layer.featureCount())
        sourceModel = QgsAttributeTableModel(layerCache)
        sourceModel.loadLayer()

        filterModel = QgsAttributeTableFilterModel(
            self.iface.mapCanvas(),
            sourceModel,
            self.dlgSplitDistricts
        )
        layerCache.setParent(filterModel)
        sourceModel.setParent(filterModel)

        attributeConfig = QgsAttributeTableConfig()
        attributeConfig.update(layer.fields())
        attributeConfig.setColumnHidden(0, True)
        filterModel.setAttributeTableConfig(attributeConfig)
        return filterModel

    def showSplitDistricts(self):
        if self.dlgSplitDistricts is None:
            self.dlgSplitDistricts = QDialog()
            self.dlgSplitDistricts.setObjectName('dlgSplitDistricts')
            self.dlgSplitDistricts.setWindowTitle(tr("Non-contiguous Districts"))
            self.dlgSplitDistricts.setAttribute(Qt.WA_DeleteOnClose, True)
            self.dlgSplitDistricts.destroyed.connect(self.deleteDialog)
            vbox = QVBoxLayout(self.dlgSplitDistricts)
            self.dlgSplitDistricts.splitsTable = QTableView(self.dlgSplitDistricts)
            self.dlgSplitDistricts.splitsTable.installEventFilter(TableViewKeyEventFilter(self.dlgSplitDistricts))
            self.dlgSplitDistricts.splitsTable.verticalHeader().hide()
            self.splitDistrictsModel = self.createSplitDistrictsModel()
            self.dlgSplitDistricts.splitsTable.setModel(self.splitDistrictsModel)
            self.dlgSplitDistricts.splitsTable.activated.connect(self.zoomToSplitDistrict)
            vbox.addWidget(self.dlgSplitDistricts.splitsTable)

        self.dlgSplitDistricts.show()

    def zoomToUnassignedGeography(self, index: QModelIndex):
        filter_id = self.unassignedGeographyModel.rowToId(index)
        fid = self.unassignedGeographyModel.layer().getFeature(filter_id)[0]
        self.iface.mapCanvas().zoomToFeatureIds(self.activePlan.assignLayer, [fid])

    def createUnassignedGeographyModel(self):
        ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(self.activePlan.assignLayer))
        expr = QgsExpression(f'{self.activePlan.distField} IS NULL OR {self.activePlan.distField} = 0')
        req = QgsFeatureRequest(expr, ctx)
        layer = self.activePlan.assignLayer.materialize(req)
        layer.setParent(self.dlgUnassignedGeography)

        attributeConfig = QgsAttributeTableConfig()
        attributeConfig.update(layer.fields())
        columns = {c.name: c for c in attributeConfig.columns()}  # pylint: disable=not-an-iterable

        for f in self.activePlan.geoFields:
            f: RdsGeoField
            if f.fieldName not in columns:
                continue

            join = f.makeJoin()
            if join is None:
                continue

            if layer.addJoin(join):
                columns[f.fieldName].hidden = True

                idx = layer.fields().count() - 1
                fld = layer.fields()[idx]
                layer.setFieldAlias(idx, f.caption)

                nameField = join.prefixedFieldName(fld)
                columns[nameField] = QgsAttributeTableConfig.ColumnConfig()
                columns[nameField].name = nameField

        attributeConfig.update(layer.fields())
        attributeConfig.setColumns(columns.values())
        layer.setFieldAlias(1, self.activePlan.geoIdCaption)
        attributeConfig.setColumnHidden(0, True)
        attributeConfig.setColumnHidden(2, True)

        cache = QgsVectorLayerCache(layer, min(1000, layer.featureCount()))
        unassignedGeographyModel = QgsAttributeTableModel(cache)
        unassignedGeographyModel.loadLayer()
        filterModel = QgsAttributeTableFilterModel(
            self.iface.mapCanvas(),
            unassignedGeographyModel,
            self.dlgUnassignedGeography
        )
        cache.setParent(filterModel)
        unassignedGeographyModel.setParent(filterModel)
        filterModel.setAttributeTableConfig(attributeConfig)
        return filterModel

    def showUnassignedGeography(self):
        if self.dlgUnassignedGeography is None:
            self.dlgUnassignedGeography = QDialog()
            self.dlgUnassignedGeography.setObjectName('dlgUnassignedGeography')
            self.dlgUnassignedGeography.setWindowTitle(tr("Unassigned Geography"))
            self.dlgUnassignedGeography.setAttribute(Qt.WA_DeleteOnClose, True)
            self.dlgUnassignedGeography.destroyed.connect(self.deleteDialog)

            vbox = QVBoxLayout(self.dlgUnassignedGeography)
            self.dlgUnassignedGeography.unassignedTable = QTableView(self.dlgUnassignedGeography)
            self.dlgUnassignedGeography.unassignedTable.installEventFilter(
                TableViewKeyEventFilter(self.dlgUnassignedGeography))
            delegate = RdsNullsAsBlanksDelegate(self.dlgUnassignedGeography.unassignedTable)
            self.dlgUnassignedGeography.unassignedTable.setItemDelegate(delegate)
            self.unassignedGeographyModel = self.createUnassignedGeographyModel()
            self.dlgUnassignedGeography.unassignedTable.setModel(self.unassignedGeographyModel)
            self.dlgUnassignedGeography.unassignedTable.verticalHeader().hide()
            self.dlgUnassignedGeography.unassignedTable.activated.connect(self.zoomToUnassignedGeography)
            vbox.addWidget(self.dlgUnassignedGeography.unassignedTable)

        self.dlgUnassignedGeography.show()

    def updateMetricsDialogs(self):
        if self.dlgSplitDistricts is not None:
            model = self.createSplitDistrictsModel()
            self.dlgSplitDistricts.splitsTable.setModel(model)
            del self.splitDistrictsModel
            self.splitDistrictsModel = model

        if self.dlgUnassignedGeography is not None:
            model = self.createUnassignedGeographyModel()
            self.dlgUnassignedGeography.unassignedTable.setModel(model)
            del self.unassignedGeographyModel
            self.unassignedGeographyModel = model
