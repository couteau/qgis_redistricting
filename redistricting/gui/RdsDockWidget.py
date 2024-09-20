from qgis.gui import QgsDockWidget
from qgis.PyQt.QtWidgets import QLabel

from ..models import RdsPlan
from ..utils import tr
from .help import showHelp
from .RdsOverlayWidget import OverlayWidget


class RdsDockWidget(QgsDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lblPlanName: QLabel
        self._plan: RdsPlan = None
        self.lblWaiting = OverlayWidget()
        self.lblWaiting.setVisible(False)
        self.helpContext: str = 'index.html'

    @property
    def plan(self) -> RdsPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RdsPlan):
        if self._plan is not None:
            self._plan.nameChanged.disconnect(self.planNameChanged)

        self._plan = value

        if self._plan is None:
            self.lblPlanName.setText(tr('No plan selected'))
        else:
            self._plan.nameChanged.connect(self.planNameChanged)
            self.lblPlanName.setText(self._plan.name)

    def planNameChanged(self, name):
        self.lblPlanName.setText(name)

    def btnHelpClicked(self):
        showHelp(self.helpContext)

    def setWaiting(self, on: bool = True):
        if self.lblWaiting.parent() is None:
            return

        if on and not self.lblWaiting.isVisible():
            self.lblWaiting.start()
        elif self.lblWaiting.isVisible():
            self.lblWaiting.stop()
