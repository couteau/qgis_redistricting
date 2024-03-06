"""QGIS Redistricting Plugin - unit tests for DistrictList class

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

from redistricting.core.District import District
from redistricting.core.DistrictList import DistrictList


class TestDistrictList:
    @pytest.fixture
    def district_list(self, plan) -> DistrictList:
        return DistrictList(plan)

    @pytest.fixture
    def district(self, district_list: DistrictList) -> District:
        return district_list['2']

    @pytest.fixture
    def dataframe(self, datadir):
        df: pd.DataFrame = pd.read_json(
            str((datadir / 'test.json').resolve())
        )
        df.set_index('district', inplace=True)  # pylint: disable=no-member
        return df

    @pytest.fixture
    def unassigned(self, district_list) -> District:
        return district_list['0']

    def test_create(self, district_list):
        assert len(district_list) == 6
        assert district_list[0].name == 'Unassigned'

    def test_contains(self, district_list, district):
        assert district in district_list
        assert 2 in district_list
        assert '2' in district_list

    def test_keys(self, district_list):
        assert list(district_list.keys()) == list(range(6))

    def test_values(self, district_list, district, unassigned):
        values = list(district_list.values())
        assert len(values) == 6
        assert values[0] == unassigned
        assert values[2] == district
        assert values[1].name == "1"

    def test_items(self, district_list):
        items = list(district_list.items())
        assert isinstance(items[0], tuple)
        assert isinstance(items[0][0], int)
        assert isinstance(items[0][1], District)

    def test_index(self, district_list, district):
        assert district_list.index(district) == 2

    def test_getitem(self, district_list, district):
        assert district_list['2'] == district
        assert district_list[2] == district
        with pytest.raises(IndexError):
            district_list[6]  # pylint: disable=pointless-statement

        with pytest.raises(IndexError):
            district_list['7']  # pylint: disable=pointless-statement

        l = district_list[1:]
        assert isinstance(l, DistrictList)
        assert len(l) == 5
        assert l[1] == district

        l = district_list['reock']
        assert isinstance(l, list)
        assert len(l) == 6

    def test_loaddata(self, district_list):
        district_list.loadData()
        assert len(district_list) == 6
        assert district_list.district[1].population == 44684

    def test_update_data(self, district_list, dataframe):
        district_list.setData(dataframe)
        assert len(district_list) == 6
        assert district_list[1].population == 44684
        assert district_list[2].population == 46916
