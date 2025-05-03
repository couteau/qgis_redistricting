from abc import abstractmethod
from functools import partial
from typing import Any

from qgis.core import (
    QgsAttributeTableConfig,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeatureRequest,
    QgsVectorLayerCache,
)
from qgis.gui import QgisInterface, QgsAttributeTableFilterModel, QgsAttributeTableModel
from qgis.PyQt.QtCore import QAbstractItemModel, QLocale, QModelIndex, QObject, Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
)
from qgis.utils import iface

from ..models import DistrictColumns, RdsGeoField, RdsMetric, RdsPlan
from ..models.metrics import RdsCompleteMetric, RdsContiguityMetric
from ..models.splitsmetric import RdsSplitsMetric
from ..utils import tr
from . import DlgSplitDetail, TableViewKeyEventFilter
from .metrics_gui import RdsMetricGuiHandler, register_metric_handler

iface: QgisInterface


class RdsNullsAsBlanksDelegate(QStyledItemDelegate):
    def displayText(self, value: Any, locale: QLocale) -> str:
        if value == 'NULL':
            return super().displayText("", locale)

        return super().displayText(value, locale)


class DialogHandler(RdsMetricGuiHandler):
    dialog: QDialog
    itemView: QAbstractItemView

    def __init__(self):
        super().__init__()
        self.dialog: QDialog = None
        self.itemView: QAbstractItemView = None

    def deleteDialog(self, dialog: QObject):
        if dialog == self.dialog:
            self.dialog = None
        self.deactivate()

    def show(self, plan: RdsPlan, metric: RdsMetric, idx: Any = None):
        super().show(plan, metric, idx)
        if self.dialog is None:
            if not self.createDialogAndView(plan, metric, idx):
                return

        self.dialog.show()

    @abstractmethod
    def createDialogAndView(self, plan: RdsPlan,  metric: RdsMetric, idx: Any) -> bool:
        ...


class AttributeTableDialogHandler(DialogHandler):
    model: QgsAttributeTableFilterModel

    def __init__(self):
        super().__init__()
        self.model: QgsAttributeTableFilterModel = None

    def createDialogAndView(self, plan, metric, idx):
        # create the dialog
        self.dialog = QDialog()
        self.dialog.setObjectName(f'dlg{metric.name()}')
        self.dialog.setWindowTitle(metric.caption())
        self.dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.dialog.destroyed.connect(self.deleteDialog)

        # create the view
        self.createView(plan, metric, idx)

        vbox = QVBoxLayout(self.dialog)
        vbox.addWidget(self.itemView)

        # create the model
        self.updateDialog(plan, metric, idx)

        return True

    @abstractmethod
    def createModel(self, plan: RdsPlan,  metric: RdsMetric, idx: Any) -> QAbstractItemModel:
        ...

    def createView(self, plan: RdsPlan, metric: RdsMetric, idx: Any):  # pylint: disable=unused-argument
        self.itemView = QTableView(self.dialog)
        self.itemView.installEventFilter(TableViewKeyEventFilter(self.dialog))
        self.itemView.setSortingEnabled(True)
        self.itemView.verticalHeader().hide()

    def updateDialog(self, plan: RdsPlan, metric: RdsMetric = None, idx: Any = None):
        if self.itemView is None:
            return

        model = self.createModel(plan, metric, idx)
        self.itemView.setModel(model)
        del self.model
        self.model = model

    def update(self, plan: RdsPlan, metric: RdsMetric = None, idx: Any = None):
        super().update(plan, metric, idx)
        self.updateDialog(plan, metric, idx)


class CompleteHandler(AttributeTableDialogHandler):
    def createView(self, plan: RdsPlan, metric: RdsMetric, idx: Any) -> QTableView:
        super().createView(plan, metric, idx)
        delegate = RdsNullsAsBlanksDelegate(self.itemView)
        self.itemView.setItemDelegate(delegate)
        self.itemView.activated.connect(partial(self.zoomToUnassignedGeography, plan=plan))

    def createModel(self, plan: RdsPlan, metric: RdsMetric, idx: Any):
        ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(plan.assignLayer))
        expr = QgsExpression(f'{plan.distField} IS NULL OR {plan.distField} = 0')
        req = QgsFeatureRequest(expr, ctx)
        layer = plan.assignLayer.materialize(req)
        layer.setParent(self.dialog)

        attributeConfig = QgsAttributeTableConfig()
        attributeConfig.update(layer.fields())
        columns = {c.name: c for c in attributeConfig.columns()}  # pylint: disable=not-an-iterable

        for f in plan.geoFields:
            f: RdsGeoField
            if f.fieldName not in columns:
                continue

            join = f.makeJoin()
            if join is None:
                continue

            if layer.addJoin(join):
                columns[f.fieldName].hidden = True

                index = layer.fields().count() - 1
                fld = layer.fields()[index]
                layer.setFieldAlias(index, f.caption)

                nameField = join.prefixedFieldName(fld)
                columns[nameField] = QgsAttributeTableConfig.ColumnConfig()
                columns[nameField].name = nameField

        attributeConfig.update(layer.fields())
        attributeConfig.setColumns(columns.values())
        layer.setFieldAlias(1, plan.geoIdCaption)
        attributeConfig.setColumnHidden(0, True)
        attributeConfig.setColumnHidden(2, True)

        cache = QgsVectorLayerCache(layer, min(1000, layer.featureCount()))
        unassignedGeographyModel = QgsAttributeTableModel(cache)
        unassignedGeographyModel.loadLayer()
        filterModel = QgsAttributeTableFilterModel(
            iface.mapCanvas(),
            unassignedGeographyModel,
            self.dialog
        )
        cache.setParent(filterModel)
        unassignedGeographyModel.setParent(filterModel)
        filterModel.setAttributeTableConfig(attributeConfig)
        return filterModel

    def zoomToUnassignedGeography(self, index: QModelIndex, plan: RdsPlan):
        filter_id = self.model.rowToId(index)
        fid = self.model.layer().getFeature(filter_id)[0]
        iface.mapCanvas().zoomToFeatureIds(plan.assignLayer, [fid])


class ContiguityHandler(AttributeTableDialogHandler):
    def createView(self, plan: RdsPlan, metric: RdsMetric, idx: Any):
        super().createView(plan, metric, idx)
        self.itemView.activated.connect(partial(self.zoomToSplitDistrict, plan=plan))

    def createModel(self, plan, metric, idx):
        ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(plan.distLayer))
        expr = QgsExpression('num_geometries(@geometry) > 1')
        req = QgsFeatureRequest(expr, ctx)
        req.setSubsetOfAttributes(
            ["fid", plan.distField, DistrictColumns.NAME, DistrictColumns.POPULATION, 'description'],
            plan.distLayer.fields())
        layer = plan.distLayer.materialize(req)
        layer.setParent(self.dialog)

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
            iface.mapCanvas(),
            sourceModel,
            self.dialog
        )
        layerCache.setParent(filterModel)
        sourceModel.setParent(filterModel)

        attributeConfig = QgsAttributeTableConfig()
        attributeConfig.update(layer.fields())
        attributeConfig.setColumnHidden(0, True)
        filterModel.setAttributeTableConfig(attributeConfig)
        return filterModel

    def zoomToSplitDistrict(self, index: QModelIndex, plan: RdsPlan):
        filter_id = self.model.rowToId(index)
        fid = self.model.layer().getFeature(filter_id)[0]
        iface.mapCanvas().zoomToFeatureIds(plan.distLayer, [fid])


class SplitsHandler(DialogHandler):
    dialog: DlgSplitDetail

    def createDialogAndView(self, plan: RdsPlan, metric: RdsMetric, idx: Any):
        if idx is None:
            return False

        self.dialog = DlgSplitDetail(
            plan,
            iface.mainWindow()
        )
        self.dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        self.dialog.destroyed.connect(self.deleteDialog)
        self.itemView = self.dialog.tvSplits

        if idx is not None:
            self.dialog.field = idx

        return True

    def update(self, plan: RdsPlan, metric: RdsMetric = None, idx: Any = None):
        if plan is None or plan != self.plan:
            self.dialog.hide()
            del self.dialog
            self.dialog = None

        super().update(plan, metric, idx)

        if plan is None:
            return

        if self.dialog is None:
            self.createDialogAndView(plan, metric, idx)

        if idx is not None:
            self.dialog.field = idx


register_metric_handler(RdsCompleteMetric, CompleteHandler)
register_metric_handler(RdsContiguityMetric, ContiguityHandler)
register_metric_handler(RdsSplitsMetric, SplitsHandler)
