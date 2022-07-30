# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - background task to calculate pending changes

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
from typing import List, Tuple, Union
from qgis.core import Qgis, QgsMessageLog


class ErrorListMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._errors = []

    def error(self) -> Union[Tuple[str, int], None]:
        return self._errors[0] if self._errors else None

    def errors(self) -> List[Tuple[str, int]]:
        return self._errors

    def hasErrors(self) -> bool:
        return bool(self._errors)

    def setError(self, error, level=Qgis.Warning):
        self._errors.clear()
        self.pushError(error, level)

    def pushError(self, error, level=Qgis.Warning):
        if isinstance(error, Exception):
            error = str(error)
        self._errors.append((error, level))
        QgsMessageLog.logMessage(error, 'Redistricting', level)

    def clearErrors(self):
        self._errors.clear()
