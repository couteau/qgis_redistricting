"""QGIS Redistricting Plugin - unit tests for District class

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
from pytestqt.plugin import QtBot

from redistricting.core import (
    District,
    RedistrictingPlan
)

# pylint: disable=no-self-use


class TestDistrict:
    @pytest.fixture
    def district(self, plan: RedistrictingPlan):
        return District(1, plan.districts)

    def test_create(self, plan: RedistrictingPlan):
        district = District(1, plan.districts)
        assert district.district == 1
        assert district.name == 'Council District 1'
        assert district.description == 'Joe Blow\'s old district'

    def test_multimember(self, plan: RedistrictingPlan):
        d = District(2, plan.districts)
        d["members"] = 2
        d["name"] = 'District 2'
        assert d.ideal == 2 * 227036 // 5

    def test_population(self, district: District):
        assert district.population == 44684

    def test_valid(self, district: District):
        assert district.isValid()

    def test_properties(self, plan: RedistrictingPlan, qtbot: QtBot):
        district = plan.districts[1]
        with qtbot.waitSignal(plan.districts.districtChanged, check_params_cb=lambda d: d == district):
            plan.districts[1].name = 'New Name'
        f = next(plan.distLayer.getFeatures(f"{plan.distField} = 1"), None)
        assert f['name'] == 'New Name'
