# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - thread debug utility

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
import sys


def debug_thread():
    if 'unittest' in sys.modules:
        try:
            import debugpy  # pylint: disable=import-outside-toplevel
            if debugpy.is_client_connected():
                debugpy.debug_this_thread()
        except:  # pylint: disable=bare-except
            pass
    else:
        try:
            import ptvsd  # pylint: disable=import-outside-toplevel
            if ptvsd.is_attached():
                ptvsd.debug_this_thread()
        except:  # pylint: disable=bare-except
            pass
