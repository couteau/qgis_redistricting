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
import importlib
import pathlib
import subprocess
import sys

from packaging.version import parse as parse_version
from qgis.gui import QgisInterface
from qgis.utils import iface

iface: QgisInterface


def install_vendor_dir():
    vendor_dir = pathlib.Path(__file__).parent.parent / "vendor"
    if vendor_dir.exists():
        sys.path.insert(0, str(vendor_dir.resolve()))


def unload_module(mod: str):
    mod_prefix = f"{mod}."
    for m in list(sys.modules.keys()):
        if m == mod or m.startswith(mod_prefix):
            del sys.modules[m]


def reload_modules():
    vendor_dir = pathlib.Path(__file__).parent.parent / "vendor"
    if vendor_dir.exists():
        for d in vendor_dir.iterdir():
            if d.suffix == '.py' or (d.is_dir() and (d / '__init__.py').exists()):
                mod = d.stem
                if mod in sys.modules:
                    unload_module(mod)

                importlib.import_module(mod)


def python_executable():
    if sys.platform == "win32":
        return pathlib.Path(sys.prefix) / 'python3.exe'

    return pathlib.Path(sys.prefix) / 'bin' / 'python3'


def install_addon(pkg: str, *options):
    installdir = pathlib.Path(__file__).parent.parent / "vendor"
    if not installdir.exists():
        installdir.mkdir()
        install_vendor_dir()

    if (installdir / pkg).exists():
        options = (*options, "--upgrade")
    try:
        subprocess.check_call([python_executable(), '-m', 'pip', 'install', '-t', str(installdir), *options, pkg])
    except subprocess.CalledProcessError:
        iface.messageBar().pushWarning("Warning", f"Could not install addon {pkg}")
        return False

    return True


def install_pyogrio():
    # pylint: disable=import-outside-toplevel
    import geopandas
    if parse_version(geopandas.__version__) < parse_version('0.12.0'):
        install_addon('geopandas')
    import shapely
    if parse_version(shapely.__version__) < parse_version('2.0.0'):
        install_addon('shapeley')

    install_addon('pyogrio')
    reload_modules()


def install_pyarrow():
    install_addon('pyarrow')
    reload_modules()


def install_gerrychain():
    install_addon('gerrychain==0.3.1')
    reload_modules()


install_vendor_dir()
