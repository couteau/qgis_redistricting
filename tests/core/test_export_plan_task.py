"""QGIS Redistricting Plugin - unit tests for ExportPlan background task

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

from redistricting.services.Tasks.ExportPlanTask import (
    ExportRedistrictingPlanTask
)


class TestExportPlanTask:
    def test_export_plan(self, mock_plan, datadir: pathlib.Path):
        t = ExportRedistrictingPlanTask(
            mock_plan,
            shapeFileName=str((datadir / 'test_export.shp').resolve()),
            equivalencyFileName=str((datadir / 'test_export.csv').resolve()))
        result = t.run()
        assert result
