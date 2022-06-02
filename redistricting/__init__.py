# -*- coding: utf-8 -*-
"""Redistricting - A QGIS plugin for building districts from geographic units

        begin                : 2022-01-15
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
        git sha              : $Format:%H$

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Create an instance of the Redistricting plugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .redistricting import Redistricting  # pylint: disable=import-outside-toplevel
    return Redistricting(iface)
