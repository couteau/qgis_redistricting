"""QGIS Redistricting Plugin - unit tests for PlanImport class

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
import redistricting.core.PlanImport


class TestPlanImport:
    @pytest.fixture
    def shapefile(self, datadir: pathlib.Path):
        return str((datadir / 'test_plan.shp').resolve())

    @pytest.fixture
    def assignmentfile(self, datadir: pathlib.Path):
        return str((datadir / 'tuscaloosa_be.csv').resolve())

    def test_import_shapefile_non_existent_file_sets_error(self, new_plan):
        p = redistricting.core.PlanImport.PlanImporter(new_plan)
        result = p.importShapefile('/notafile.txt', 'district')
        assert not result
        msg, _ = p.error()
        assert re.search('not exist', msg)

    def test_import_shapefile_bad_shapefile_sets_error(self, new_plan, datadir):
        p = redistricting.core.PlanImport.PlanImporter(new_plan)
        result = p.importShapefile(str(datadir / 'tuscaloosa_be.csv'), 'district')
        assert not result
        msg, _ = p.error()
        assert re.search('Invalid shapefile', msg)

    def test_import_shapefile(self, new_plan, shapefile, mocker: MockerFixture):
        task = mocker.patch('redistricting.core.PlanImport.ImportShapeFileTask')
        add = mocker.patch.object(redistricting.core.PlanImport.QgsApplication.taskManager(), 'addTask')
        p = redistricting.core.PlanImport.PlanImporter(new_plan)
        p.importShapefile(shapefile, 'district')
        task.assert_called_once()
        add.assert_called_once()

    def test_import_assignments_non_existent_file_sets_error(self, new_plan):
        p = redistricting.core.PlanImport.PlanImporter(new_plan)
        result = p.importAssignments('/notafile.txt')
        assert not result
        msg, _ = p.error()
        assert re.search('not exist', msg)

    def test_import_assignments(self, new_plan, assignmentfile, mocker: MockerFixture):
        task = mocker.patch('redistricting.core.PlanImport.ImportAssignmentFileTask')
        add = mocker.patch.object(redistricting.core.PlanImport.QgsApplication.taskManager(), 'addTask')
        p = redistricting.core.PlanImport.PlanImporter(new_plan)
        p.importAssignments(assignmentfile)
        task.assert_called_once()
        add.assert_called_once()
