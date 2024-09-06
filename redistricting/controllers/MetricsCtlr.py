from typing import Optional

from pytest_qgis import QgsProject
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QToolBar

from ..gui import DlgSplitDetail
from ..models import (
    RdsGeoField,
    RdsPlan
)
from ..services import (
    ActionRegistry,
    PlanManager
)
from .BaseCtlr import BaseController


class MetricsController(BaseController):
    def __init__(self, iface: QgisInterface, project: QgsProject, planManager: PlanManager, toolbar: QToolBar, parent: Optional[QObject] = None):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.dlgSplits: DlgSplitDetail = None
        self.actions = ActionRegistry()
        self.actionShowSplitsDialog = self.actions.createAction(
            name="actionShowSplitsDialog",
            icon=':/plugins/redistricting/copydistrict.svg',
            text=self.tr("Split detail"),
            callback=self.showSplits
        )

    def load(self):
        self.planManager.activePlanChanged.connect(self.planChanged)

    def unload(self):
        self.planManager.activePlanChanged.disconnect(self.planChanged)

    def planChanged(self, plan: RdsPlan):
        if self.dlgSplits:
            self.dlgSplits.close()
            self.dlgSplits = None
        self.actionShowSplitsDialog.setEnabled(plan is not None)

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
