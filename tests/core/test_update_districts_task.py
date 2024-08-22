"""QGIS Redistricting Plugin - unit tests for updating changes background task

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
from pytest_mock import MockerFixture

from redistricting.models.Plan import RdsPlan
from redistricting.services.Tasks.UpdateDistrictsTask import (
    AggregateDistrictDataTask
)


class TestUpdateDistrictsTask:

    @pytest.fixture(scope="class", autouse=True)
    def patch_task(self, class_mocker: MockerFixture):
        class_mocker.patch.object(AggregateDistrictDataTask, "setDependentLayers")

    def test_create(self, mock_plan: RdsPlan):
        t = AggregateDistrictDataTask(mock_plan)
        assert t.exception is None
        assert not t.updateDistricts

    def test_run(self, plan: RdsPlan):
        t = AggregateDistrictDataTask(plan)
        t.run()
        assert t.exception is None
        assert t.data is not None

    def test_run_subset(self, plan: RdsPlan):
        t = AggregateDistrictDataTask(plan, [2, 3])
        result = t.run()
        assert result
        assert t.data is not None
        assert t.exception is None
        assert len(t.data.index) == 2
        assert t.totalPopulation == 227036

    def test_finished(self, plan: RdsPlan):
        t = AggregateDistrictDataTask(plan, [2, 3])
        t.run()
        t.finished(True)
