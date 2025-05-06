"""QGIS Redistricting Plugin - thread debug utility

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

import os
import sys

DEBUG = os.getenv("DEBUG")


def debug_thread():
    if not DEBUG or "PYTEST_CURRENT_TEST" in os.environ:
        # Don't debug if not in DEBUG mode or if running pytest
        return

    if "unittest" in sys.modules:
        try:
            import debugpy  # type: ignore  # pylint: disable=import-outside-toplevel

            if debugpy.is_client_connected():
                debugpy.debug_this_thread()
        except ImportError:
            pass
    else:
        try:
            import debugpy  # type: ignore  # pylint: disable=import-outside-toplevel

            if debugpy.is_client_connected():
                debugpy.debug_this_thread()
        except ImportError:
            try:
                import ptvsd  # type: ignore  # pylint: disable=import-outside-toplevel

                if ptvsd.is_attached():
                    ptvsd.debug_this_thread()
            except ImportError:  # pylint: disable=bare-except
                pass
