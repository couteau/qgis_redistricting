"""QGIS Redistricting Plugin - base controller class

        begin                : 2024-03-20
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
from abc import abstractmethod
from typing import (
    TYPE_CHECKING,
    Optional
)
from collections.abc import Iterable

from qgis.core import (
    Qgis,
    QgsProject
)
from qgis.gui import (
    QgisInterface,
    QgsDockWidget
)
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QObject,
    Qt
)
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QProgressDialog,
    QToolBar
)

from ..services import (
    ActionRegistry,
    ErrorListMixin,
    PlanManager
)
from ..utils import tr

if TYPE_CHECKING:
    from qgis.PyQt.QtCore import QT_VERSION
    if QT_VERSION >= 0x060000:
        from PyQt6.QtGui import QAction  # type: ignore[import]
    else:
        from PyQt5.QtWidgets import QAction  # type: ignore[import]

else:
    from qgis.PyQt.QtGui import QAction


class RdsProgressDialog(QProgressDialog):
    """wrapper class to prevent dialog from being re-shown after it is
    cancelled if updates arrive from another thread after cancel is called
    """

    def setValue(self, progress: int):
        if self.wasCanceled():
            return

        super().setValue(progress)


class BaseController(QObject):
    def __init__(
            self,
            iface: QgisInterface,
            project: QgsProject,
            planManager: PlanManager,
            toolbar: QToolBar,
            parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.actions = ActionRegistry()
        self.iface = iface
        self.project = project
        self.planManager = planManager
        self.toolbar = toolbar
        self.dlg = None
        self.errorList = None

    @abstractmethod
    def load(self):
        ...

    @abstractmethod
    def unload(self):
        ...

    def progressCanceled(self):
        """Hide progress dialog and display message on cancel"""
        if self.errorList:
            errors = self.errorList.errors()
        else:
            errors = [(f"{self.dlg.labelText()} canceled", Qgis.MessageLevel.Warning)]

        if errors:
            self.pushErrors(errors, tr("Canceled"), Qgis.MessageLevel.Warning)

        self.dlg.canceled.disconnect(self.progressCanceled)
        self.dlg.close()
        self.dlg = None

    def startProgress(self, text=None, maximum=100, canCancel=True, errorList: ErrorListMixin = None):
        """Create and initialize a progress dialog"""
        self.errorList = errorList
        if self.dlg:
            self.dlg.cancel()
        self.dlg = RdsProgressDialog(
            text, tr("Cancel"),
            0, maximum,
            self.iface.mainWindow(),
            Qt.WindowType.WindowStaysOnTopHint)
        if not canCancel:
            self.dlg.setCancelButton(None)
        else:
            self.dlg.canceled.connect(self.progressCanceled)

        self.dlg.setValue(0)
        return self.dlg

    def endProgress(self, progress: QProgressDialog = None):
        QCoreApplication.instance().processEvents()
        if progress is None:
            progress = self.dlg

        if progress is not None:
            progress.canceled.disconnect(self.progressCanceled)
            progress.close()

        if self.dlg == progress:
            self.dlg = None

    def pushErrors(self, errors: Iterable[tuple[str, int]], title: str = None, level: int = None):
        if not errors:
            return

        if title is None:
            title = tr("Error")

        msg, lvl = errors[0]
        if level is None:
            level = lvl

        if len(errors) > 1:
            self.iface.messageBar().pushMessage(
                title,
                msg,
                showMore="\n".join(e[0] for e in errors),
                level=level,
                duration=5
            )
        else:
            self.iface.messageBar().pushMessage(
                title,
                msg,
                level=level,
                duration=5
            )

    def checkActivePlan(self, action):
        if self.planManager.activePlan is None:
            self.iface.messageBar().pushMessage(
                tr("Oops!"),
                tr(f"Cannot {action}: no active redistricting plan. Try creating a new plan."),
                level=Qgis.MessageLevel.Warning
            )
            return False

        return True

    @property
    def activePlan(self):
        return self.planManager.activePlan


class DockWidgetController(BaseController):
    """Controller that manages a QDockWidget"""

    def __init__(
        self,
        iface: QgisInterface,
        project: QgsProject,
        planManager: PlanManager,
        toolbar: QToolBar,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.dockwidget: QDockWidget = None
        self.actionToggle: QAction = None
        self.defaultArea = Qt.DockWidgetArea.BottomDockWidgetArea

    @abstractmethod
    def createDockWidget(self) -> QgsDockWidget:
        pass

    def createToggleAction(self) -> QAction:
        if self.dockwidget is None:
            return None

        if isinstance(self.dockwidget, QgsDockWidget):
            action = QAction(self.dockwidget)
            self.dockwidget.setToggleVisibilityAction(action)
        else:
            action = self.dockwidget.toggleViewAction()

        return action

    def load(self):
        self.dockwidget = self.createDockWidget()
        self.iface.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dockwidget)
        self.actionToggle = self.createToggleAction()
        self.actions.registerAction(f"actionToggle{self.dockwidget.objectName()}", self.actionToggle)
        self.toolbar.addAction(self.actionToggle)

    def unload(self):
        self.toolbar.removeAction(self.actionToggle)
        self.iface.removeDockWidget(self.dockwidget)
        self.dockwidget.setParent(None)
        self.dockwidget.destroy(True, True)
        self.dockwidget = None
        self.actionToggle = None
