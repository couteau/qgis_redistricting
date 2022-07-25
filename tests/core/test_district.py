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
from redistricting.core import RedistrictingPlan, District
from redistricting.core.District import Unassigned

# pylint: disable=no-self-use


class TestDistrict:
    @pytest.fixture
    def district(self, plan) -> District:
        return plan.districts[1]

    @pytest.fixture
    def new_district(self, plan) -> District:
        return District(plan, 1, name='District 1', description='Joe Blow\'s old district')

    @pytest.fixture
    def unassigned(self, plan) -> Unassigned:
        return Unassigned(plan)

    @pytest.fixture
    def multimember_district(self, plan):
        return District(plan, 2, 'District 2', 2, '2 member district')

    def test_create(self, new_district: District):
        assert new_district.district == 1
        assert new_district.name == 'District 1'
        assert new_district.description == 'Joe Blow\'s old district'
        assert new_district.ideal == 227036 // 5

    def test_loadfromtable(self, district: District):
        assert district.district == 1
        assert district.name == 'Council District 1'
        assert district.description == ''

    def test_multimember(self, multimember_district: District):
        assert multimember_district.ideal == 2 * 227036 // 5

    def test_unassigned(self, unassigned: Unassigned):
        assert unassigned.deviation is None
        assert unassigned.name == 'Unassigned'
        assert unassigned.district == 0

    def test_serialize(self, district: District):
        data = district.serialize()
        assert data == {
            'district': 1,
            'name': 'Council District 1',
            'description': '',
            'members': 1
        }

    def test_population(self, district: District):
        assert district.population == 44684

    def test_update(self, new_district: District):
        assert new_district.population != 44684
        data = {
            'pop_total': 44684,
            'vap_total': 34563,
            'vap_nh_white': 24274,
            'vap_nh_black': 7296,
            'vap_apblack': 7580,
            'polsbypopper': 0.329727825720102,
            'reock': 0.39253075886413,
            'convexhull': 0.768313485094759
        }
        new_district.update(data)
        assert new_district.population == 44684
        assert hasattr(new_district, 'pct_vap_apblack') and new_district.pct_vap_apblack == 7580 / 34563
        assert new_district.polsbyPopper == 0.329727825720102

    def test_valid(self, district: District, new_district: District):
        assert district.valid
        assert not new_district.valid

    def test_properties(self, plan: RedistrictingPlan, qtbot: QtBot):
        with qtbot.waitSignal(plan.planChanged, check_params_cb=lambda p, f, n, o: f == 'district.name'):
            plan.districts[1].name = 'New Name'
        f = next(plan.distLayer.getFeatures(f"{plan.distField} = 1"), None)
        assert f['name'] == 'New Name'
