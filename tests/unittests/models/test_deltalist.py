"""QGIS Redistricting Plugin - unit tests for DeltaList class

Copyright 2022-2024, Stuart C. Naifeh

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
import pandas as pd
import pytest

from redistricting.models import (
    Delta,
    DeltaList
)

# pylint: disable=no-self-use


class TestDeltaList:
    @pytest.fixture
    def empty_delta_list(self) -> DeltaList:
        return DeltaList()

    @pytest.fixture
    def delta_list(self, empty_delta_list: DeltaList):
        df = pd.DataFrame.from_records(
            [{
                'district': 1,
                'pop_total': 100,
                'vap_total': 80,
                'vap_nh_black': 20,
                'vap_apblack': 25,
                'vap_nh_white': 40
            }]
        )
        df.set_index('district', drop=False, inplace=True)
        empty_delta_list.setData(df)  # pylint: disable=protected-access
        return empty_delta_list

    def test_create(self, empty_delta_list: DeltaList):
        assert len(empty_delta_list) == 0

    def test_clear(self, delta_list: DeltaList):
        delta_list.clear()
        assert len(delta_list) == 0

    def test_getitem(self, delta_list: DeltaList):
        assert delta_list['1'] == delta_list[0]
        assert isinstance(delta_list[0], Delta)
        assert delta_list[0, 0] == 1
        assert delta_list[0, 1] == 100
        assert delta_list['vap_total'] == [80]
