# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RdFileWidget
        A QgsFileWidget with a property that can be used for a QWizard field
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
from qgis.PyQt.QtCore import pyqtProperty
from qgis.gui import QgsFileWidget


class RdsFileWidget(QgsFileWidget):
    @pyqtProperty(str)
    def path(self):
        return self.filePath()

    @path.setter
    def path(self, value):
        self.setFilePath(value)
