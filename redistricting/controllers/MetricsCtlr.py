from typing import (
    Any,
    Optional
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
    QObject
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
    TableViewKeyEventFilter
)
from ..models import (
    DistrictColumns,
    RdsGeoField,
    RdsPlan
)
from ..services import (
    ActionRegistry,
    PlanManager
)
from ..utils import tr
from .BaseCtlr import BaseController


class RdsNullsAsBlanksDelegate(QStyledItemDelegate):
    def displayText(self, value: Any, locale: QLocale) -> str:
        if value == 'NULL':
            return super().displayText("", locale)

        return super().displayText(value, locale)


class MetricsController(BaseController):
    def __init__(self, iface: QgisInterface, project: QgsProject, planManager: PlanManager, toolbar: QToolBar, parent: Optional[QObject] = None):
        super().__init__(iface, project, planManager, toolbar, parent)
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

    def load(self):
        self.planManager.activePlanChanged.connect(self.planChanged)
        self.planManager.planAdded.connect(self.planAdded)
        self.planManager.planRemoved.connect(self.planRemoved)

    def unload(self):
        self.planManager.planRemoved.disconnect(self.planRemoved)
        self.planManager.planAdded.disconnect(self.planAdded)
        self.planManager.activePlanChanged.disconnect(self.planChanged)

    def planChanged(self, plan: RdsPlan):
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

    def planAdded(self, plan: RdsPlan):
        plan.metricsChanged.connect(self.updateMetricsDialogs)

    def planRemoved(self, plan: RdsPlan):
        plan.metricsChanged.disconnect(self.updateMetricsDialogs)

    def showSplits(self, field: Optional[RdsGeoField] = None):
        if not isinstance(field, RdsGeoField):
            field = self.sender().data()

        if field is None:
            return

        if self.dlgSplits is not None:
            self.dlgSplits.geoField = field
        else:
            self.dlgSplits = DlgSplitDetail(self.planManager.activePlan, field, self.iface.mainWindow())
        self.dlgSplits.show()

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
            self.dlgSplitDistricts.setWindowTitle(tr("Non-contiguous Districts"))
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
            self.dlgUnassignedGeography.setWindowTitle(tr("Unassigned Geography"))

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
