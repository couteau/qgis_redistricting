# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - install additional python packages

        begin                : 2024-02-01
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
import json
import pathlib
import shutil
import sys
from functools import lru_cache

import requests
from packaging.version import parse as parse_version
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import (
    QProcess,
    QStandardPaths
)
from qgis.utils import iface

iface: QgisInterface


def vendor_dir():
    return pathlib.Path(__file__).parent.parent / "vendor"


def install_vendor_dir():
    # create a startup.py file that will add the vendor directory to the path
    # before other python code loads modules we have overridden
    homePath = QStandardPaths.standardLocations(QStandardPaths.AppDataLocation)
    if len(homePath) > 0:
        startuppy = pathlib.Path(homePath[0]) / 'startup.py'
        with startuppy.open("a+") as f:
            f.seek(0)
            lines = f.readlines()
            if not "import sys\n" in lines:
                lines.insert(0, "import sys\n")
            insert_path = f"sys.path.insert(0, {str(vendor_dir().resolve())!r})\n"
            if not insert_path in lines:
                lines.append(insert_path)
            f.truncate()
            f.writelines(lines)

    sys.path.insert(0, str(vendor_dir().resolve()))


def uninstall_vendor_dir():
    homePath = QStandardPaths.standardLocations(QStandardPaths.AppDataLocation)
    if len(homePath) > 0:
        startuppy = pathlib.Path(homePath[0]) / 'startup.py'
        if startuppy.exists():
            f = startuppy.open("r+")
            lines = f.readlines()
            insert_path = f"sys.path.insert(0, {str(vendor_dir().resolve())!r})\n"
            if insert_path in lines:
                lines.remove(insert_path)
                if len(lines) == 1 and lines[0] == "import sys\n":
                    f.close()
                    startuppy.unlink()
                else:
                    f.truncate()
                    f.write(lines)
                    f.close()


def uninstall_all():
    d = vendor_dir()
    if d.exists():
        shutil.rmtree(str(d))
        if str(vendor_dir) in sys.path:
            sys.path.remove(str(d))

        uninstall_vendor_dir()


def python_executable():
    if sys.platform == "win32":
        return pathlib.Path(sys.prefix) / 'python3.exe'

    return pathlib.Path(sys.prefix) / 'bin' / 'python3'


@lru_cache
def check_new_version(pkg: str):
    if not pkg in sys.modules:
        return False

    current_version = sys.modules[pkg].__version__

    # Check pypi for the latest version number
    try:
        r = requests.get(f'https://pypi.org/pypi/{pkg}/json', timeout=5)
        contents = r.content.decode()
        data = json.loads(contents)
        latest_version = data['info']['version']
    except TimeoutError:
        return False

    return parse_version(latest_version) > parse_version(current_version)


def install_addon(pkg: str, *options):
    installdir = vendor_dir()
    if not installdir.exists():
        installdir.mkdir()
        install_vendor_dir()

    if (installdir / pkg).exists():
        options = (*options, "--upgrade")

    process = QProcess(iface.mainWindow())
    process.setProgram(str(python_executable()))
    process.setArguments(['-m', 'pip', 'install', '-t', str(installdir), *options, pkg])
    process.start()
    return process


def install_pyogrio():
    pkgs = []
    # pylint: disable=import-outside-toplevel
    import geopandas
    if parse_version(geopandas.__version__) < parse_version('0.12.0'):
        pkgs.append('geopandas')

    import shapely
    if parse_version(shapely.__version__) < parse_version('2.0.0'):
        pkgs.append('shapely')

    return install_addon('pyogrio', *pkgs)


def install_pyarrow():
    return install_addon('pyarrow')


def install_gerrychain():
    return install_addon('gerrychain==0.3.1')
