"""QGIS Redistricting Plugin - Settins page in QGIS global settings

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

from qgis.gui import QgsCollapsibleGroupBox, QgsOptionsPageWidget, QgsOptionsWidgetFactory
from qgis.PyQt.QtCore import QProcess
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QCheckBox, QGridLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

from .. import settings
from ..utils import addons, tr


class RdsOptionsFactory(QgsOptionsWidgetFactory):
    def icon(self):
        return QIcon(":/plugins/redistricting/icon.png")

    def createWidget(self, parent):
        return RdsConfigOptionsPage(parent)


class RdsConfigOptionsPage(QgsOptionsPageWidget):
    def __init__(self, parent):  # noqa: PLR0915
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        self.gbMetrics = QgsCollapsibleGroupBox(tr("Metrics"), self)
        main_layout.addWidget(self.gbMetrics)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        self.gbMetrics.setLayout(layout)
        self.cbEnableCutEdges = QCheckBox(tr("Enable Calculation of Cut Edges"), self)
        self.cbEnableCutEdges.setToolTip(
            tr("Calculate cut edges plan-wide compactness score for primary geographic units.")
        )
        self.cbEnableCutEdges.setChecked(settings.enableCutEdges)
        layout.addWidget(self.cbEnableCutEdges)
        self.cbEnableSplitDetail = QCheckBox(tr("Enable Calculation of Split Geographies"), self)
        self.cbEnableSplitDetail.setChecked(settings.enableSplits)
        layout.addWidget(self.cbEnableSplitDetail)

        self.gbAddons = QgsCollapsibleGroupBox(tr("Addons"), self)
        main_layout.addWidget(self.gbAddons)
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setVerticalSpacing(12)
        layout.setColumnStretch(1, 1)
        self.gbAddons.setLayout(layout)

        label = QLabel(
            tr(
                "Redistricting Plugin can benefit from the use of python packages "
                "that are not installed with the typical QGIS installation or "
                "in the prepackaged MacOS and Windows versions of QGIS. "
                "Redistricting Plugin can install these packages in a separate "
                "directory that will not affect your python environment and can "
                "be cleanly removed. Installing these options through the Redistricting Plugin "
                "settings is recommended when you are using a prepackaged QGIS installer on "
                "MacOS or Windows. If you are in Linux or installed QGIS through a package "
                "manager such as Anaconda, it is recommended that you use your package manager to "
                "install these addons."
            ),
            self,
        )
        label.setWordWrap(True)
        label.setStyleSheet("QLabel { color: cornflowerblue; }")
        layout.addWidget(label, 0, 0, 1, 2)

        self.btnInstallPyogrio = QPushButton(tr("Install pyogrio"), self)
        self.btnInstallPyogrio.setEnabled(self.canInstallPyogrio())
        if self.btnInstallPyogrio.isEnabled():
            self.btnInstallPyogrio.setToolTip(tr("Click to install pyogrio in the QGIS python environment"))
        else:
            self.btnInstallPyogrio.setToolTip(tr("pyogrio package is already installed"))
        self.btnInstallPyogrio.clicked.connect(self.installPackage)
        layout.addWidget(self.btnInstallPyogrio, 2, 0)
        label = QLabel(tr("Redistricting Plugin can use the pyogrio package to improve performance"), self)
        label.setWordWrap(True)
        layout.addWidget(label, 2, 1)

        self.btnInstallPyarrow = QPushButton(tr("Install pyarrow"), self)
        self.btnInstallPyarrow.setEnabled(self.canInstallPyarrow())
        if self.btnInstallPyarrow.isEnabled():
            self.btnInstallPyarrow.setToolTip(
                tr("Click to install pyarrow in the QGIS python environment. Requires pyogrio.")
            )
        elif self.canInstallPyarrow():
            self.btnInstallPyarrow.setToolTip(tr("payarrow package is already installed"))

        self.btnInstallPyarrow.clicked.connect(self.installPackage)
        layout.addWidget(self.btnInstallPyarrow, 3, 0)
        label = QLabel(tr("Redistricting Plugin can use the pyarrow package to improve performance"), self)
        label.setWordWrap(True)
        layout.addWidget(label, 3, 1)

        self.lblStdOut = QTextEdit(readOnly=True)
        self.lblStdOut.setVisible(False)
        layout.addWidget(self.lblStdOut, 4, 0, 1, 2)
        self.lblRestart = QLabel(tr("Please restart QGIS for package changes to take effect"))
        self.lblRestart.setStyleSheet("QLabel { color: red; }")
        self.lblRestart.setVisible(False)
        layout.addWidget(self.lblRestart, 5, 0, 1, 2)
        self.btnUninstallAll = QPushButton(tr("Uninstall all addons"))
        self.btnUninstallAll.setToolTip(tr("Uninstall all addons installed by Redistricting Plugin"))
        self.btnUninstallAll.clicked.connect(self.uninstallAll)
        self.btnUninstallAll.setEnabled(addons.vendor_dir().exists())
        layout.addWidget(self.btnUninstallAll, 6, 0, 1, 2)

        main_layout.addStretch()

    def apply(self):
        settings.enableCutEdges = self.cbEnableCutEdges.isChecked()
        settings.enableSplits = self.cbEnableSplitDetail.isChecked()
        settings.saveSettings()

    # pylint: disable=import-outside-toplevel, unused-import
    def canInstallPyogrio(self):
        if (addons.vendor_dir() / "pyogrio").exists():
            return addons.check_new_version("pyogrio")

        try:
            import pyogrio  # type: ignore # noqa

            return False
        except ImportError:
            return True

    def canInstallPyarrow(self):
        if (addons.vendor_dir() / "pyarrow").exists():
            return addons.check_new_version("pyarrow")

        try:
            import pyarrow  # type: ignore # noqa

            return False
        except ImportError:
            return True

    def uninstallAll(self):
        addons.uninstall_all()
        self.lblRestart.hide()
        self.btnInstallPyogrio.setEnabled(not self.canInstallPyogrio())
        self.btnInstallPyarrow.setEnabled(self.canInstallPyogrio() and not self.canInstallPyarrow())
        self.lblRestart.show()

    def updateOutput(self):
        process: QProcess = self.sender()
        text = process.readAllStandardOutput().data().decode()
        self.lblStdOut.append(text)

    def installComplete(self):
        process: QProcess = self.sender()

        if process.exitCode() != 0:
            self.lblRestart.setText(tr("An error occurred"))

        self.lblRestart.show()

        self.btnInstallPyogrio.setEnabled(not self.canInstallPyogrio())
        self.btnInstallPyarrow.setEnabled(self.canInstallPyogrio() and not self.canInstallPyarrow())
        self.btnUninstallAll.setEnabled(True)

    def installPackage(self):
        btn = self.sender()
        if btn == self.btnInstallPyogrio:
            fn = addons.install_pyogrio
        elif btn == self.btnInstallPyarrow:
            fn = addons.install_pyarrow
        else:
            fn = None

        self.btnInstallPyogrio.setEnabled(False)
        self.btnInstallPyarrow.setEnabled(False)
        self.btnUninstallAll.setEnabled(False)

        if fn is not None:
            self.lblStdOut.setText("")
            self.lblStdOut.show()
            process = fn()
            process.setParent(self)
            process.readyReadStandardOutput.connect(self.updateOutput)
            process.finished.connect(self.installComplete)
