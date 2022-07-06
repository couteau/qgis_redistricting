"""QGIS Redistricting Plugin - unit tests for PlanImport class"""
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
