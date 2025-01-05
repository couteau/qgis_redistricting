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
import pytest
from pytest_mock import MockerFixture

from redistricting.models.base.lists import KeyedList
from redistricting.models.columns import MetricsColumns
from redistricting.models.field import RdsGeoField
from redistricting.models.plan import RdsMetrics
from redistricting.models.splits import RdsSplits

# pylint: disable=protected-access


class TestPlanStats:

    @pytest.fixture
    def mock_splits(self, mocker: MockerFixture):
        l = mocker.create_autospec(spec=KeyedList)
        l.__len__.return_value = 1
        l.__getitem__.return_value = mocker.create_autospec(spec=RdsSplits)

    def test_create(self, mock_plan, mocker: MockerFixture):
        districts = type(mock_plan).districts
        districts.__getitem__.return_value = [0.5]
        geofields = type(mock_plan).geoFields
        geofields.__iter__.return_value = [mocker.create_autospec(spec=RdsGeoField, instance=True)]
        stats = RdsMetrics(mock_plan)
        assert stats.cutEdges is None
        for f in MetricsColumns.CompactnessScores():
            assert getattr(stats, f) == 0.5
        assert len(stats.splits) == 1

    def test_create_with_cutedges_and_splits(self, mock_splits):
        stats = RdsMetrics(2013, mock_splits)
        assert stats.cutEdges == 2013
