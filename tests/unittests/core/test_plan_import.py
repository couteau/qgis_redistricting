"""QGIS Redistricting Plugin - unit tests for PlanImport class

Copyright (C) 2025, Stuart C. Naifeh

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
import re

import pytest
from pytest_mock.plugin import MockerFixture

import redistricting.services.planimport


class TestPlanImport:
    @pytest.fixture
    def shapefile(self, datadir: pathlib.Path):
        return str((datadir / "test_plan.shp").resolve())

    @pytest.fixture
    def assignmentfile(self, datadir: pathlib.Path):
        return str((datadir / "tuscaloosa_be.csv").resolve())

    def test_import_shapefile_non_existent_file_sets_error(self, new_plan):
        p = redistricting.services.planimport.ShapefileImporter()
        p.setSourceFile("/notafile.txt")
        p.setDistField("district")
        result = p.importPlan(new_plan)
        assert not result
        msg, _ = p.error()  # pylint: disable=unpacking-non-sequence
        assert msg is not None
        assert re.search("not exist", msg)

    def test_import_shapefile_bad_shapefile_sets_error(self, new_plan, datadir):
        p = redistricting.services.planimport.ShapefileImporter()
        p.setSourceFile(datadir / "tuscaloosa_be.csv")
        p.setDistField("district")
        result = p.importPlan(new_plan)
        assert not result
        msg, _ = p.error()  # pylint: disable=unpacking-non-sequence
        assert re.search("Invalid shapefile", msg)

    def test_import_shapefile(self, new_plan, shapefile, mocker: MockerFixture):
        task = mocker.patch("redistricting.services.planimport.ImportShapeFileTask")
        add = mocker.patch.object(redistricting.services.planimport.QgsApplication.taskManager(), "addTask")
        p = redistricting.services.planimport.ShapefileImporter()
        p.setSourceFile(shapefile)
        p.setDistField("district")
        p.importPlan(new_plan)
        task.assert_called_once()
        add.assert_called_once()
        p.deleteLater()

    def test_import_assignments_non_existent_file_sets_error(self, new_plan):
        p = redistricting.services.planimport.AssignmentImporter()
        p.setSourceFile("/notafile.txt")
        result = p.importPlan(new_plan)
        assert not result
        msg, _ = p.error()  # pylint: disable=unpacking-non-sequence
        assert re.search("not exist", msg)
        p.deleteLater()

    def test_import_assignments(self, new_plan, assignmentfile, mocker: MockerFixture):
        task = mocker.patch("redistricting.services.planimport.ImportAssignmentFileTask")
        add = mocker.patch.object(redistricting.services.planimport.QgsApplication.taskManager(), "addTask")
        p = redistricting.services.planimport.AssignmentImporter()
        p.setSourceFile(assignmentfile)
        p.importPlan(new_plan)
        task.assert_called_once()
        add.assert_called_once()
