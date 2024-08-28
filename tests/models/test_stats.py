"""QGIS Redistricting Plugin - unit tests for PlanStats class

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
from pytest_mock import MockerFixture

from redistricting.models.columns import StatsColumns
from redistricting.models.Field import RdsGeoField
from redistricting.models.Plan import RdsPlanMetrics

# pylint: disable=protected-access


class TestPlanStats:

    def test_create(self, mock_plan, mocker: MockerFixture):
        districts = type(mock_plan).districts
        districts.__getitem__.return_value = [0.5]
        geofields = type(mock_plan).geoFields
        geofields.__iter__.return_value = [mocker.create_autospec(spec=RdsGeoField, instance=True)]
        stats = RdsPlanMetrics(mock_plan)
        assert stats.cutEdges is None
        for f in StatsColumns.CompactnessScores():
            assert getattr(stats, f) == 0.5
        assert len(stats.splits) == 1
