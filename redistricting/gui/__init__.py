"""QGIS Redistricting Plugin - UI classes and utilities module

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
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

from qgis.PyQt.QtCore import QEvent, QObject, Qt
from qgis.PyQt.QtGui import QKeyEvent
from qgis.PyQt.QtWidgets import QTableView

from .dlgcopy import DlgCopyPlan
from .dlgdelete import DlgConfirmDelete

# Dialogs and Dock Widgets
from .dlgedit import DlgEditPlan
from .dlgeditdistrict import DlgNewDistrict
from .dlgexport import DlgExportPlan
from .dlgimportequivalency import DlgImportPlan
from .dlgimportshape import DlgImportShape
from .dlgplanmgr import DlgSelectPlan
from .dlgsplits import DlgSplitDetail
from .dwdistrict import DockDistrictDataTable
from .dwedit import DockRedistrictingToolbox
from .dwmetrics import DockPlanMetrics
from .dwpending import DockPendingChanges
from .metrics_gui import RdsMetricGuiHandler, get_metric_handler, register_metric_handler
from .painttool import PaintDistrictsTool, PaintMode


class TableViewKeyEventFilter(QObject):
    def eventFilter(self, obj: QTableView, event: QKeyEvent):  # pylint: disable=unused-argument
        if event.type() != QEvent.Type.KeyPress:
            return False

        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            obj.activated.emit(obj.currentIndex())
            return True

        return False


__all__ = [
    "DlgEditPlan",
    "DlgCopyPlan",
    "DlgSelectPlan",
    "DlgSplitDetail",
    "DlgExportPlan",
    "DlgImportPlan",
    "DlgImportShape",
    "DlgNewDistrict",
    "DlgConfirmDelete",
    "DockRedistrictingToolbox",
    "DockDistrictDataTable",
    "DockPendingChanges",
    "DockPlanMetrics",
    "PaintDistrictsTool",
    "PaintMode",
    "RdsMetricGuiHandler",
    "get_metric_handler",
    "register_metric_handler",
]
