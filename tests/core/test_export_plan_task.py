"""QGIS Redistricting Plugin - unit tests for RedistrictingPlan class"""
import pathlib

from redistricting.core.Tasks.ExportPlanTask import ExportRedistrictingPlanTask


class TestExportPlanTask:
    def test_export_plan(self, plan, datadir: pathlib.Path):
        t = ExportRedistrictingPlanTask(
            plan,
            shapeFileName=str((datadir / 'test_export.shp').resolve()),
            equivalencyFileName=str((datadir / 'test_export.csv').resolve()))
        result = t.run()
        assert result
