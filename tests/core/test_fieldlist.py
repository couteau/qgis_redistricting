"""QGIS Redistricting Plugin - unit tests for FieldList class

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

from redistricting.core.Field import Field
from redistricting.core.FieldList import FieldList

# pylint: disable=no-self-use


class TestFieldList:
    @pytest.fixture
    def field(self, block_layer):
        return Field(block_layer, 'vap_nh_black')

    @pytest.fixture
    def empty_field_list(self) -> FieldList:
        return FieldList()

    @pytest.fixture
    def field_list(self, empty_field_list: FieldList, field) -> FieldList:
        empty_field_list.append(field)
        return empty_field_list

    def test_createempty(self):
        l = FieldList()
        assert len(l) == 0

    def test_createfromlist(self, field):
        l = FieldList([field])
        assert len(l) == 1

    def test_append(self, empty_field_list, field):
        empty_field_list.append(field)
        assert len(empty_field_list) == 1
        assert empty_field_list[0] == field

    def test_insert(self, field_list, block_layer, field):
        field2 = Field(block_layer, 'vap_nh_white')
        field_list.insert(0, field2)
        assert field_list[0] == field2
        assert field_list[1] == field

    def test_slice(self, field_list, block_layer, field):
        field2 = Field(block_layer, 'vap_nh_white')
        field_list.append(field2)
        assert field_list[1:] == [field2]
        assert field_list[0:1] == [field]

    def test_extend_list(self, field_list, block_layer, field):
        field2 = Field(block_layer, 'vap_nh_white')
        field_list.extend([field2])
        assert field_list[0] == field
        assert field_list[1] == field2

    def test_extend_fieldlist(self, field_list, block_layer, field):
        field2 = Field(block_layer, 'vap_nh_white')
        field_list2 = FieldList([field2])
        field_list.extend(field_list2)
        assert field_list[0] == field
        assert field_list[1] == field2

    def test_del_int(self, field_list):
        del field_list[0]
        assert len(field_list) == 0

    def test_remove(self, field_list, field):
        field_list.remove(field)
        assert len(field_list) == 0

    def test_clear(self, field_list):
        field_list.clear()
        assert len(field_list) == 0

    def test_move(self, field_list, field, block_layer):
        field2 = Field(block_layer, 'vap_nh_white')
        field_list.append(field2)
        field_list.move(0, 1)
        assert field_list[0] == field2 and field_list[1] == field

    def test_iadd_item(self, empty_field_list, field):
        empty_field_list += field
        assert len(empty_field_list) == 1

    def test_iadd_list(self, empty_field_list, field):
        empty_field_list += [field]
        assert len(empty_field_list) == 1

    def test_contains_string(self, field_list):
        assert 'vap_nh_black' in field_list

    def test_contains_field(self, field, field_list):
        assert field in field_list

    def test_index_int(self, field, field_list):
        assert field_list[0] == field

    def test_index_str(self, field, field_list):
        assert field_list['vap_nh_black'] == field

    def test_list_equality_list(self, field, field_list):
        assert field_list == [field]

    def test_list_equality_fieldlist(self, field, field_list):
        assert field_list == FieldList([field])
