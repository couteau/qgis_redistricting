# -*- coding: utf-8 -*-
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
from qgis.PyQt.QtCore import (
    QEvent,
    QObject,
    Qt
)
from qgis.PyQt.QtGui import QKeyEvent
from qgis.PyQt.QtWidgets import QTableView

from .DistrictDataTable import DockDistrictDataTable
from .DistrictTools import DockRedistrictingToolbox
from .DlgConfirmDelete import DlgConfirmDelete
from .DlgCopyPlan import DlgCopyPlan
# Dialogs and Dock Widgets
from .DlgEditPlan import DlgEditPlan
from .DlgExportPlan import DlgExportPlan
from .DlgImportPlan import DlgImportPlan
from .DlgImportShape import DlgImportShape
from .DlgNewDistrict import DlgNewDistrict
from .DlgSelectPlan import DlgSelectPlan
from .DlgSplits import DlgSplitDetail
from .PaintTool import (
    PaintDistrictsTool,
    PaintMode
)
from .PendingChanges import DockPendingChanges
from .PlanMetrics import DockPlanMetrics


class TableViewKeyEventFilter(QObject):
    def eventFilter(self, obj: QTableView, event: QKeyEvent):  # pylint: disable=unused-argument
        if event.type() != QEvent.KeyPress:
            return False

        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            obj.activated.emit(obj.currentIndex())
            return True

        return False


__all__ = [
    'DlgEditPlan',
    'DlgCopyPlan',
    'DlgSelectPlan',
    'DlgSplitDetail',
    'DlgExportPlan',
    'DlgImportPlan',
    'DlgImportShape',
    'DlgNewDistrict',
    'DlgConfirmDelete',
    'DockRedistrictingToolbox',
    'DockDistrictDataTable',
    'DockPendingChanges',
    'DockPlanMetrics',
    'PaintDistrictsTool',
    'PaintMode',
]
