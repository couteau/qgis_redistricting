"""QGIS Redistricting Plugin - unit tests for District class

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
import pytest

from redistricting.models import (
    RdsDistrict,
    RdsUnassigned
)


class TestDistrict:
    @pytest.fixture
    def district(self):
        return RdsDistrict(1)

    def test_create(self):
        district = RdsDistrict(1)
        assert district.district == 1
        assert district.name == "1"
        assert district.members == 1
        assert district.description == ""
        assert district.population == 0
        assert district.deviation == 0
        assert district.pct_deviation == 0

        with pytest.raises(TypeError):
            district = RdsDistrict()

    def test_create_with_name_sets_name(self):
        district = RdsDistrict(1, name="District 1")
        assert district.name == "District 1"

    def test_create_with_members_sets_members(self):
        district = RdsDistrict(1, members=2)
        assert district.members == 2

    def test_create_with_description_sets_description(self):
        district = RdsDistrict(1, description="District 1 description")
        assert district.description == "District 1 description"

    def test_multimember(self):
        d = RdsDistrict(1, members=2)
        assert d.members == 2

    def test_population(self, district: RdsDistrict):
        assert district.population == 0

    def test_set_property_modifies_property(self, district: RdsDistrict):
        district.name = 'New Name'
        assert district.name == 'New Name'
        district.description = "Discrict description"
        assert district.description == "Discrict description"

    def test_getitem_int_getsitem(self, district: RdsDistrict):
        assert district[0] == 1
        assert district[1] == "1"
        assert district[2] == 1

    def test_set_district_raises_exception(self, district: RdsDistrict):
        with pytest.raises(AttributeError):
            district.district = 2

        with pytest.raises(IndexError):
            district["district"] = 2

        with pytest.raises(IndexError):
            district[0] = 2

    def test_create_unassigned(self):
        district = RdsUnassigned()
        assert district.district == 0
        assert district.name == "Unassigned"
        assert district.population == 0
        assert district.members is None
        assert district.deviation is None
        assert district.pct_deviation is None

    def test_unassigned_set_name_raises_exception(self):
        district = RdsUnassigned()
        with pytest.raises(AttributeError):
            district.name = "New Name"
