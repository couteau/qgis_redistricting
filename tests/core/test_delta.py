"""QGIS Redistricting Plugin - unit tests for Delta class

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
from redistricting.core.Delta import Delta

from redistricting.core.Plan import RedistrictingPlan

# pylint: disable=no-self-use


class TestDelta:
    @pytest.fixture
    def delta(self, plan: RedistrictingPlan):
        return Delta(plan, plan.districts[1], {
            'pop_total': 100,
            'vap_total': 80,
            'vap_nh_black': 20,
            'vap_apblack': 25,
            'vap_nh_white': 40
        })

    def test_create(self, delta: Delta):
        assert delta.district == 1
