
# Form implementation generated from reading ui file '/Users/stuart/Source/qgis_redistricting/ui/DlgImportShapefile.ui'
#
# Created by: PyQt5 UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from qgis import gui
from qgis.PyQt import (
    QtCore,
    QtGui,
    QtWidgets
)


class Ui_dlgImportShapefile(object):
    def setupUi(self, dlgImportShapefile):
        dlgImportShapefile.setObjectName("dlgImportShapefile")
        dlgImportShapefile.resize(362, 201)
        dlgImportShapefile.setMinimumSize(QtCore.QSize(254, 133))
        self.gridLayout = QtWidgets.QGridLayout(dlgImportShapefile)
        self.gridLayout.setObjectName("gridLayout")
        self.lblDistField = QtWidgets.QLabel(dlgImportShapefile)
        self.lblDistField.setObjectName("lblDistField")
        self.gridLayout.addWidget(self.lblDistField, 1, 0, 1, 1)
        self.cmbDistField = gui.QgsFieldComboBox(dlgImportShapefile)
        self.cmbDistField.setObjectName("cmbDistField")
        self.gridLayout.addWidget(self.cmbDistField, 1, 1, 1, 1)
        self.lblShapefile = QtWidgets.QLabel(dlgImportShapefile)
        self.lblShapefile.setObjectName("lblShapefile")
        self.gridLayout.addWidget(self.lblShapefile, 0, 0, 1, 1)
        self.cmbNameField = gui.QgsFieldComboBox(dlgImportShapefile)
        self.cmbNameField.setAllowEmptyFieldName(True)
        self.cmbNameField.setObjectName("cmbNameField")
        self.gridLayout.addWidget(self.cmbNameField, 2, 1, 1, 1)
        self.fwShapefile = gui.QgsFileWidget(dlgImportShapefile)
        self.fwShapefile.setObjectName("fwShapefile")
        self.gridLayout.addWidget(self.fwShapefile, 0, 1, 1, 1)
        self.lblNameField = QtWidgets.QLabel(dlgImportShapefile)
        self.lblNameField.setObjectName("lblNameField")
        self.gridLayout.addWidget(self.lblNameField, 2, 0, 1, 1)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum,
                                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.gridLayout.addItem(spacerItem, 7, 0, 1, 2)
        self.buttonBox = QtWidgets.QDialogButtonBox(dlgImportShapefile)
        self.buttonBox.setEnabled(True)
        self.buttonBox.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.StandardButton.Cancel |
                                          QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.gridLayout.addWidget(self.buttonBox, 8, 0, 1, 2)
        self.lblMembersField = QtWidgets.QLabel(dlgImportShapefile)
        self.lblMembersField.setObjectName("lblMembersField")
        self.gridLayout.addWidget(self.lblMembersField, 3, 0, 1, 1)
        self.cmbMembersField = gui.QgsFieldComboBox(dlgImportShapefile)
        self.cmbMembersField.setAllowEmptyFieldName(True)
        self.cmbMembersField.setObjectName("cmbMembersField")
        self.gridLayout.addWidget(self.cmbMembersField, 3, 1, 1, 1)
        self.lblDistField.setBuddy(self.cmbDistField)
        self.lblShapefile.setBuddy(self.fwShapefile)
        self.lblNameField.setBuddy(self.cmbNameField)
        self.lblMembersField.setBuddy(self.cmbMembersField)

        self.retranslateUi(dlgImportShapefile)
        self.buttonBox.accepted.connect(dlgImportShapefile.accept)
        self.buttonBox.rejected.connect(dlgImportShapefile.reject)
        QtCore.QMetaObject.connectSlotsByName(dlgImportShapefile)

    def retranslateUi(self, dlgImportShapefile):
        _translate = QtCore.QCoreApplication.translate
        dlgImportShapefile.setWindowTitle(_translate("dlgImportShapefile", "Import Shapefile"))
        dlgImportShapefile.setToolTip(_translate("dlgImportShapefile", "Import assingments from a shapefile"))
        self.lblDistField.setText(_translate("dlgImportShapefile", "District &Field"))
        self.cmbDistField.setToolTip(_translate(
            "dlgImportShapefile", "Shapefile attribute containing the district number"))
        self.lblShapefile.setText(_translate("dlgImportShapefile", "&Shapefile"))
        self.cmbNameField.setToolTip(_translate(
            "dlgImportShapefile", "Shapefile attribute containing the district name"))
        self.fwShapefile.setDialogTitle(_translate("dlgImportShapefile", "Import Shapefile"))
        self.fwShapefile.setFilter(_translate("dlgImportShapefile", "*.shp"))
        self.lblNameField.setText(_translate("dlgImportShapefile", "&Name Field"))
        self.lblMembersField.setText(_translate("dlgImportShapefile", "&Member Field"))
        self.cmbMembersField.setToolTip(_translate(
            "dlgImportShapefile", "Shapefile attribute containing the number of members in the district"))
