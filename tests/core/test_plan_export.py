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
import pytest
from pytest_mock.plugin import MockerFixture
import redistricting
from redistricting.core import PlanExporter


class TestPlanExport:
    @pytest.fixture
    def export(self, plan, datadir):
        return PlanExporter(
            plan,
            datadir / 'test.csv',
            datadir / 'test.shp',
            None,
            True,
            True,
            True
        )

    def test_export(self, export: PlanExporter, mocker: MockerFixture):
        task = mocker.patch('redistricting.core.PlanExport.ExportRedistrictingPlanTask')
        add = mocker.patch.object(redistricting.core.PlanExport.QgsApplication.taskManager(), 'addTask')
        export.export()
        task.assert_called_once()
        add.assert_called_once()
