# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - internationalization utilities

        begin                : 2024-03-20
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
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
    Optional,
    overload
)

from qgis.PyQt.QtCore import QCoreApplication


@overload
def tr(message: str) -> str:
    pass


@overload
def tr(context: str, message: str) -> str:
    pass


def tr(ctx_or_msg: str, message: Optional[str] = None) -> str:
    """Get the translation for a string using Qt translation API.

            :param ctx_or_msg: Translation context or string for translation.
            :type message: str, QString

            :param message: String for translation.
            :type message: str, QString

            :returns: Translated version of message.
            :rtype: QString
            """
    if message is None:
        message = ctx_or_msg
        ctx_or_msg = 'redistricting'
    return QCoreApplication.translate(ctx_or_msg, message)
