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
from typing import (
    Iterable,
    Union
)

from qgis.core import (
    Qgis,
    QgsMessageLog
)


class ErrorListMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._errors = []

    def error(self) -> Union[tuple[str, int], None]:
        """Retrieve the first error pushed onto the error stack, if any
        :returns: Error message and message level tuple
        """
        return self._errors[0] if self._errors else None

    def errors(self) -> list[tuple[str, int]]:
        """Retrieve the list of errors set on the object
        :returns: A list of error message and message level tuples
        """
        return self._errors

    def hasErrors(self) -> bool:
        """Whether the object has encountered any errors
        """
        return bool(self._errors)

    def setError(self, error: Union[str, Exception], level: Qgis.MessageLevel = Qgis.Warning):
        """Clear the error list and push the passed error
        :param error: the error to set on the object
        :param level: the message level for the error: Info, Warning, Critical, etc.
        """
        self._errors.clear()
        self.pushError(error, level)

    def pushErrors(self, errors: Iterable[Union[str, Exception]], level: Qgis.MessageLevel = Qgis.Warning):
        """
        Push the passed error onto the error list for the object and
        log it to the Qgis message log with the "Redistricting" tag
        :param error: the error to set on the object
        :param level: the message level for the error: Info, Warning, Critical, etc.
        """
        for error in errors:
            if isinstance(error, Exception):
                error = str(error)
            self._errors.append((error, level))
            QgsMessageLog.logMessage(error, 'Redistricting', level)

    def pushError(self, error: Union[str, Exception], level: Qgis.MessageLevel = Qgis.Warning):
        """
        Push the passed error onto the error list for the object and
        log it to the Qgis message log with the "Redistricting" tag
        :param error: the error to set on the object
        :param level: the message level for the error: Info, Warning, Critical, etc.
        """
        self.pushErrors((error,), level)

    def clearErrors(self):
        self._errors.clear()
