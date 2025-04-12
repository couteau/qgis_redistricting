# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/stuart/Source/qgis_redistricting/ui/DlgExportPlan.ui'
#
# Created by: qgis.PyQt UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from qgis import gui
from qgis.PyQt import (
    QtCore,
    QtGui,
    QtWidgets
)


class Ui_dlgExportPlan(object):
    def setupUi(self, dlgExportPlan):
        dlgExportPlan.setObjectName("dlgExportPlan")
        dlgExportPlan.resize(335, 357)
        dlgExportPlan.setMinimumSize(QtCore.QSize(254, 320))
        self.verticalLayout = QtWidgets.QVBoxLayout(dlgExportPlan)
        self.verticalLayout.setObjectName("verticalLayout")
        self.gbxEquivalency = QtWidgets.QGroupBox(dlgExportPlan)
        self.gbxEquivalency.setObjectName("gbxEquivalency")
        self.gridLayout = QtWidgets.QGridLayout(self.gbxEquivalency)
        self.gridLayout.setObjectName("gridLayout")
        self.cmbGeography = QtWidgets.QComboBox(self.gbxEquivalency)
        self.cmbGeography.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.cmbGeography.sizePolicy().hasHeightForWidth())
        self.cmbGeography.setSizePolicy(sizePolicy)
        self.cmbGeography.setObjectName("cmbGeography")
        self.gridLayout.addWidget(self.cmbGeography, 2, 1, 1, 1)
        self.lblGeography = QtWidgets.QLabel(self.gbxEquivalency)
        self.lblGeography.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lblGeography.sizePolicy().hasHeightForWidth())
        self.lblGeography.setSizePolicy(sizePolicy)
        self.lblGeography.setObjectName("lblGeography")
        self.gridLayout.addWidget(self.lblGeography, 2, 0, 1, 1)
        self.fwEquivalency = gui.QgsFileWidget(self.gbxEquivalency)
        self.fwEquivalency.setEnabled(True)
        self.fwEquivalency.setFilter("*.csv")
        self.fwEquivalency.setStorageMode(gui.QgsFileWidget.SaveFile)
        self.fwEquivalency.setObjectName("fwEquivalency")
        self.gridLayout.addWidget(self.fwEquivalency, 1, 0, 1, 2)
        self.cbxExportEquivalency = QtWidgets.QCheckBox(self.gbxEquivalency)
        self.cbxExportEquivalency.setObjectName("cbxExportEquivalency")
        self.gridLayout.addWidget(self.cbxExportEquivalency, 0, 0, 1, 2)
        self.verticalLayout.addWidget(self.gbxEquivalency)
        self.gbxShape = QtWidgets.QGroupBox(dlgExportPlan)
        self.gbxShape.setObjectName("gbxShape")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.gbxShape)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.cbxExportShape = QtWidgets.QCheckBox(self.gbxShape)
        self.cbxExportShape.setObjectName("cbxExportShape")
        self.verticalLayout_3.addWidget(self.cbxExportShape)
        self.fwShape = gui.QgsFileWidget(self.gbxShape)
        self.fwShape.setEnabled(True)
        self.fwShape.setFilter("*.shp")
        self.fwShape.setStorageMode(gui.QgsFileWidget.SaveFile)
        self.fwShape.setObjectName("fwShape")
        self.verticalLayout_3.addWidget(self.fwShape)
        self.cbxIncludeUnassigned = QtWidgets.QCheckBox(self.gbxShape)
        self.cbxIncludeUnassigned.setEnabled(False)
        self.cbxIncludeUnassigned.setChecked(True)
        self.cbxIncludeUnassigned.setObjectName("cbxIncludeUnassigned")
        self.verticalLayout_3.addWidget(self.cbxIncludeUnassigned)
        self.cbxDemographics = QtWidgets.QCheckBox(self.gbxShape)
        self.cbxDemographics.setEnabled(False)
        self.cbxDemographics.setChecked(True)
        self.cbxDemographics.setObjectName("cbxDemographics")
        self.verticalLayout_3.addWidget(self.cbxDemographics)
        self.cbxMetrics = QtWidgets.QCheckBox(self.gbxShape)
        self.cbxMetrics.setEnabled(False)
        self.cbxMetrics.setChecked(True)
        self.cbxMetrics.setObjectName("cbxMetrics")
        self.verticalLayout_3.addWidget(self.cbxMetrics)
        self.verticalLayout.addWidget(self.gbxShape)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum,
                                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.buttonBox = QtWidgets.QDialogButtonBox(dlgExportPlan)
        self.buttonBox.setEnabled(True)
        self.buttonBox.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.StandardButton.Cancel |
                                          QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)
        self.lblGeography.setBuddy(self.cmbGeography)

        self.retranslateUi(dlgExportPlan)
        self.buttonBox.accepted.connect(dlgExportPlan.accept)
        self.buttonBox.rejected.connect(dlgExportPlan.reject)
        self.cbxExportShape.toggled['bool'].connect(self.cbxDemographics.setEnabled)
        self.cbxExportShape.toggled['bool'].connect(self.cbxMetrics.setEnabled)
        self.cbxExportShape.toggled['bool'].connect(self.cbxIncludeUnassigned.setEnabled)
        self.cbxExportEquivalency.toggled['bool'].connect(self.cmbGeography.setEnabled)
        self.cbxExportEquivalency.toggled['bool'].connect(self.lblGeography.setEnabled)
        QtCore.QMetaObject.connectSlotsByName(dlgExportPlan)

    def retranslateUi(self, dlgExportPlan):
        _translate = QtCore.QCoreApplication.translate
        dlgExportPlan.setWindowTitle(_translate("dlgExportPlan", "Export Plan"))
        self.gbxEquivalency.setTitle(_translate("dlgExportPlan", "Equivalency File"))
        self.lblGeography.setText(_translate("dlgExportPlan", "Geography"))
        self.fwEquivalency.setDialogTitle(_translate("dlgExportPlan", "Equivalency File"))
        self.cbxExportEquivalency.setText(_translate("dlgExportPlan", "Export Equivalency File"))
        self.gbxShape.setTitle(_translate("dlgExportPlan", "Shapefile"))
        self.cbxExportShape.setText(_translate("dlgExportPlan", "Export Shapefile"))
        self.fwShape.setDialogTitle(_translate("dlgExportPlan", "Shapefile"))
        self.cbxIncludeUnassigned.setText(_translate("dlgExportPlan", "Include unassigned geography"))
        self.cbxDemographics.setText(_translate("dlgExportPlan", "Include demographics"))
        self.cbxMetrics.setText(_translate("dlgExportPlan", "Include metrics"))
