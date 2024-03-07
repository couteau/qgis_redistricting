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
from redistricting.core.Plan import RedistrictingPlan
from redistricting.core.Tasks.UpdateDistrictsTask import (
    AggregateDistrictDataTask
)


class TestUpdateDistrictsTask:

    def test_create(self, plan: RedistrictingPlan):
        t = AggregateDistrictDataTask(plan)
        assert t.exception is None
        assert not t.updateDistricts

    def test_run(self, plan: RedistrictingPlan):
        t = AggregateDistrictDataTask(plan)
        t.run()
        assert t.data is not None

    def test_run_subset(self, plan: RedistrictingPlan):
        t = AggregateDistrictDataTask(plan, [2, 3])
        result = t.run()
        assert result
        assert t.data is not None
        assert t.exception is None
        assert len(t.data.index) == 2
        assert t.totalPopulation == 227036
        # t.finished(True)
