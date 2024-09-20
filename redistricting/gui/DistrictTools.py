# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - QDockWidget with tools for painting districts

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
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QUndoStack

from ..models import RdsPlan
from .RdsDockWidget import RdsDockWidget
from .ui.DistrictTools import Ui_qdwDistrictTools


class DockRedistrictingToolbox(Ui_qdwDistrictTools, RdsDockWidget):

    _plan: RdsPlan = None
    geoFieldChanged = pyqtSignal(int)
    sourceChanged = pyqtSignal(int)
    targetChanged = pyqtSignal(int)

    def __init__(self, plan=None, parent=None):
        super(DockRedistrictingToolbox, self).__init__(parent)
        self.setupUi(self)

        self.cmbGeoSelect.currentIndexChanged.connect(self.geoFieldChanged)
        self.cmbTarget.currentIndexChanged.connect(self.targetChanged)
        self.cmbSource.currentIndexChanged.connect(self.sourceChanged)

        self.btnUndo.setIcon(QgsApplication.getThemeIcon('/mActionUndo.svg'))
        self.btnRedo.setIcon(QgsApplication.getThemeIcon('/mActionRedo.svg'))
        self.btnUndo.setEnabled(False)
        self.btnRedo.setEnabled(False)

        self.helpContext = 'usage/toolbox.html'
        self.btnHelp.setIcon(QgsApplication.getThemeIcon('/mActionHelpContents.svg'))
        self.btnHelp.clicked.connect(self.btnHelpClicked)

        self._undoStack: QUndoStack = None

        self.plan = plan

    @RdsDockWidget.plan.setter
    def plan(self, value: RdsPlan):
        RdsDockWidget.plan.fset(self, value)
        if self._plan:
            self.undoStack = self._plan.assignLayer.undoStack()
        else:
            self.undoStack = None

        self.cmbSource.setEnabled(self._plan is not None)
        self.cmbTarget.setEnabled(self._plan is not None)
        self.cmbGeoSelect.setEnabled(self._plan is not None)

    @property
    def undoStack(self):
        return self._undoStack

    @undoStack.setter
    def undoStack(self, value: QUndoStack):
        self._undoStack = value
        if self._undoStack is not None:
            self.undoAction = self._undoStack.createUndoAction(self)
            self.undoAction.setIcon(QgsApplication.getThemeIcon('/mActionUndo.svg'))
            self.redoAction = self._undoStack.createRedoAction(self)
            self.redoAction.setIcon(QgsApplication.getThemeIcon('/mActionRedo.svg'))
        else:
            self.undoAction = None
            self.redoAction = None

        self.btnUndo.setDefaultAction(self.undoAction)
        self.btnRedo.setDefaultAction(self.redoAction)
