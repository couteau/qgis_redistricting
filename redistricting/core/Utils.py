# -*- coding: utf-8 -*-
"""QGIS Redistricting plugin utility functions and background tasks

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import annotations

import sys
import os
import sqlite3
import re
from typing import TYPE_CHECKING, List, Union

from qgis.core import QgsVectorLayer
from qgis.PyQt.QtCore import QCoreApplication

if TYPE_CHECKING:
    from . import Field


def tr(context, message=None):
    """Get the translation for a string using Qt translation API.

            :param message: String for translation.
            :type message: str, QString

            :returns: Translated version of message.
            :rtype: QString
            """
    if message is None:
        message = context
        context = 'Redistricting'
    return QCoreApplication.translate(context, message)


def loadSpatialiteModule(db: sqlite3.Connection):
    """Load the sqlite spatialite module in the context of the passed sqlite connection

            :param db: Sqlite3 connection object
            :type db: sqlite3.Connection

            :returns: Whether the module was successfully loaded
            :rtype: Boolean
            """
    if sys.platform == 'win32':
        path = os.path.join(sys.prefix, 'Library', 'bin', 'mod_spatialite.dll')
    elif sys.platform == 'darwin':
        path = os.path.join(sys.prefix, 'lib', 'mod_spatialite.dylib')
        if not os.path.exists(path):
            path = os.path.join(sys.prefix, 'lib', 'mod_spatialite.so')
    elif sys.platform.startswith('linux'):
        # LD_LIBRARY_PATH not set on Linux.
        path = os.path.expandvars('$PREFIX/lib/mod_spatialite.so')
    else:
        raise Exception(f'Cannot recognize platform {sys.platform!r}')

    if not os.path.exists(path):
        path = 'mod_spatialite'

    try:
        db.enable_load_extension(True)
        db.execute("SELECT load_extension(?)", [path])
        db.enable_load_extension(False)
        return True
    except:  # pylint: disable=bare-except
        return False


def makeFieldName(field: Field):
    if field.isExpression:
        name = (field.caption or field.field).lower()
        if not name.isidentifier():
            name = re.sub(r'[^\w]+', '_', name)
    else:
        name = field.field

    return name


def getDefaultField(layer: QgsVectorLayer, fieldList: List[Union[str, re.Pattern]]):
    for f in fieldList:
        if isinstance(f, str):
            if (i := layer.fields().lookupField(f)) != -1:
                return layer.fields()[i].name()
        elif isinstance(f, re.Pattern):
            for fld in layer.fields():
                if f.match(fld.name()):
                    return fld.name()

    return None
