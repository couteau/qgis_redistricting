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
import pathlib
import subprocess
import sys

from packaging.version import parse as parse_version

# from pip import main as pipmain


def python_executable():
    if sys.platform == "win32":
        return pathlib.Path(sys.prefix) / 'python3.exe'

    return pathlib.Path(sys.prefix) / 'bin' / 'python3'


def install_addon(pkg: str, *options):
    installdir = pathlib.Path(__file__).parent.parent / "vendor"
    if not installdir.exists():
        installdir.mkdir()
    if (installdir / pkg).exists():
        options = (*options, "--upgrade")
    subprocess.check_call([python_executable(), '-m', 'pip', 'install', '-t', str(installdir), *options, pkg])
    # pipmain(['install', '-t', str(installdir), *options, pkg])


def install_pyogrio():
    import geopandas
    if parse_version(geopandas.__version__) < parse_version('0.12.0'):
        install_addon('geopandas', "--no-deps")
    import shapely
    if parse_version(shapely.__version__) < parse_version('2.0.0'):
        install_addon('shapeley', "--no-deps")

    install_addon('pyogrio', '--no-deps')


def install_pyarrow():
    install_addon('pyarrow', '--no-deps')


def install_gerrychain():
    install_addon('gerrychain', '--no-deps')
