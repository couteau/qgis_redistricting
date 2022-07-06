"""QGIS Redistricting Plugin - unit tests for RedistrictingPlan class"""
import pathlib
from redistricting.core.Tasks.ImportShapeTask import ImportShapeFileTask


class TestImportShapeFileTask:
    def test_import_shapefile(self, mock_plan, datadir: pathlib.Path):
        t = ImportShapeFileTask(mock_plan, str((datadir / 'test_plan.shp').resolve()), 'district')
        result = t.run()
        assert result
        assert len(t.errors) == 0
