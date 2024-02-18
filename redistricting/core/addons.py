# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - install additional python packages

        begin                : 2022-06-01
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
import pathlib
import subprocess

# from pip import main as pipmain


def python_executable():
    return pathlib.Path(os.__file__).parents[2] / 'bin' / 'python'


def install_addon(pkg: str, *options):
    installdir = pathlib.Path(__file__).parent.parent / "vendor"
    if not installdir.exists():
        installdir.mkdir()
    if (installdir / pkg).exists():
        options = (*options, "--upgrade")
    subprocess.check_call([python_executable(), '-m', 'pip', 'install', '-t', str(installdir), *options, pkg])
    # pipmain(['install', '-t', str(installdir), *options, pkg])


def install_pyogrio():
    install_addon('pyogrio', '--no-deps')


def install_pyarrow():
    install_addon('pyarrow', '--no-deps')


def install_gerrychain():
    install_addon('gerrychain', '--no-deps')
