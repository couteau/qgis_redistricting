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
import pytest

from redistricting.models import (
    District,
    DistrictList
)


class TestDistrictList:
    @pytest.fixture
    def district(self):
        district = District(2, name="District 2")
        return district

    @pytest.fixture
    def district_list_with_district(self, district):
        district_list = DistrictList()
        district_list.numDistricts = 2
        district_list.append(district)
        return district_list

    def test_create(self):
        district_list = DistrictList()
        assert len(district_list) == 1
        assert district_list[0].name == 'Unassigned'
        assert district_list.byindex[0].name == 'Unassigned'

    def test_access_nonexistent_district_raises_error(self):
        district_list = DistrictList()
        with pytest.raises(KeyError):
            district_list[1]  # pylint: disable=pointless-statement

    def test_add_district_allows_access_by_district_number(self, district_list_with_district, district):
        assert district_list_with_district[2] == district

    def add_district_allows_access_by_index(self, district_list_with_district, district):
        assert district_list_with_district.byindex[1] == district

    def add_district_allows_access_by_byname(self, district_list_with_district, district):
        assert district_list_with_district.byname["District 2"] == district

    def test_contains(self, district_list_with_district, district):
        assert district in district_list_with_district
        assert 2 in district_list_with_district

    def test_keys(self, district_list_with_district):
        assert list(district_list_with_district.keys()) == [0, 2]

    def test_values(self, district_list_with_district, district):
        values = list(district_list_with_district.values())
        assert len(values) == 2
        assert values[1] == district

    def test_items(self):
        district_list = DistrictList()
        items = list(district_list.items())
        assert isinstance(items[0], tuple)
        assert isinstance(items[0][0], int)
        assert isinstance(items[0][1], District)

    def test_index(self, district_list_with_district, district):
        assert district_list_with_district.index(district) == 1

    def test_getitem(self, district_list_with_district, district):
        assert district_list_with_district[2] is district
        with pytest.raises(KeyError):
            district_list_with_district[3]  # pylint: disable=pointless-statement

        with pytest.raises(ValueError):
            district_list_with_district['3']  # pylint: disable=pointless-statement

    def test_getitem_slice_returns_district_list(self, district_list_with_district, district):
        l = district_list_with_district[1:]
        assert isinstance(l, DistrictList)
        assert len(l) == 1
        assert l.byindex[0] == district

    def test_getitem_slice_returns_value_list(self, district_list_with_district):
        l = district_list_with_district[0:2, 'deviation']
        assert isinstance(l, list)
        assert len(l) == 2
