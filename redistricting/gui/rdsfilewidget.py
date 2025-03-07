# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - A QgsFileWidget with a property that can be 
        used for a QWizard field

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
from qgis.gui import QgsFileWidget
from qgis.PyQt.QtCore import pyqtProperty


class RdsFileWidget(QgsFileWidget):
    @pyqtProperty(str)
    def path(self):
        return self.filePath()

    @path.setter
    def path(self, value):
        self.setFilePath(value)
