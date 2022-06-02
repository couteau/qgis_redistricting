# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DockDistrictDataTable
        A QDockWidget that shows selected demographic data for the active
        Redistricting Plan
                              -------------------
        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import io
import csv
from qgis.PyQt.QtCore import Qt, QObject, QCoreApplication, QEvent, QModelIndex
from qgis.PyQt.QtGui import QKeySequence
from qgis.PyQt.QtWidgets import QDockWidget, QDialog, QWizard
from qgis.core import QgsApplication
from ..core import RedistrictingPlan, DistrictDataModel
from .RdsOverlayWidget import OverlayWidget
from .ui.DistrictDataTable import Ui_qdwDistrictData
from ._dlgEditPlanFieldPage import dlgEditPlanFieldPage


class DockDistrictDataTable(Ui_qdwDistrictData, QDockWidget):
    @property
    def plan(self) -> RedistrictingPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RedistrictingPlan):
        self._plan = value
        self._model.plan = value
        if self._plan is None:
            self.btnAddFields.setEnabled(False)
            self.btnRecalculate.setEnabled(False)
            self.lblPlanName.setText(QCoreApplication.translate('Redistricting', 'No plan selected'))
        else:
            self.btnAddFields.setEnabled(True)
            self.btnRecalculate.setEnabled(True)
            self.lblPlanName.setText(self._plan.name)

    def __init__(self, plan: RedistrictingPlan, parent: QObject = None):
        super().__init__(parent)
        self.setupUi(self)

        self.tblDataTable.installEventFilter(self)
        self.lblWaiting = OverlayWidget(self.tblDataTable)
        self.lblWaiting.setVisible(False)

        self._model = DistrictDataModel(None, self)
        self._model.modelAboutToBeReset.connect(self.lblWaiting.show)
        self._model.modelReset.connect(self.lblWaiting.hide)
        self.tblDataTable.setModel(self._model)

        self.btnCopy.setIcon(
            QgsApplication.getThemeIcon('/mActionEditCopy.svg'))
        self.btnCopy.clicked.connect(self.copyToClipboard)
        self.btnRecalculate.setIcon(
            QgsApplication.getThemeIcon('/mActionRefresh.svg'))
        self.btnRecalculate.clicked.connect(self.recalculate)
        self.btnAddFields.setIcon(
            QgsApplication.getThemeIcon('/mActionAddManualTable.svg'))
        self.btnAddFields.clicked.connect(self.addFieldDlg)

        self._plan: RedistrictingPlan = None
        self.plan = plan

    def addFieldDlg(self):
        w = QWizard()
        w.setWindowTitle(QCoreApplication.translate(
            'Redistricting', 'Add/Edit Data Fields'))
        w.wizardStyle = QWizard.ModernStyle
        w.setOptions(QWizard.NoBackButtonOnStartPage |
                     QWizard.NoDefaultButton)

        w.addPage(dlgEditPlanFieldPage(self))
        w.setField('dataFields', list(self._plan.dataFields))
        if w.exec_() == QDialog.Accepted:
            self._plan.dataFields = w.field('dataFields')

    def recalculate(self):
        self._plan.districts.resetData(immediate=True)

    def copyToClipboard(self):
        """Copy district data to clipboard in csv format"""
        m: DistrictDataModel = self.tblDataTable.model()
        t = []
        r = []
        for h in range(0, m.columnCount()):
            r.append(f'"{m.headerData(h, Qt.Horizontal, Qt.DisplayRole)}"')

        t.append(r)
        for row in range(1, self.plan.numDistricts+1):
            r = []
            for col in range(m.columnCount()):
                index = m.index(row, col, QModelIndex())
                v = m.data(index, Qt.DisplayRole)
                v = v if v is not None else ''
                r.append(f'"{v}"')
            t.append(r)

        cb = QgsApplication.instance().clipboard()
        text = os.linesep.join([','.join(r) for r in t])
        cb.setText(text)

    def copySelection(self):
        selection = self.tblDataTable.selectedIndexes()
        if selection:
            rows = sorted(index.row() for index in selection)
            columns = sorted(index.column() for index in selection)
            rowcount = rows[-1] - rows[0] + 1
            colcount = columns[-1] - columns[0] + 1
            table = [[''] * colcount for _ in range(rowcount)]
            for index in selection:
                row = index.row() - rows[0]
                column = index.column() - columns[0]
                table[row][column] = index.data()
            stream = io.StringIO()
            csv.writer(stream, delimiter='\t').writerows(table)
            QgsApplication.instance().clipboard().setText(stream.getvalue())
        return

    def eventFilter(self, source, event):
        if (event.type() == QEvent.KeyPress and
                event.matches(QKeySequence.Copy)):
            self.copySelection()
            return True
        return super().eventFilter(source, event)
