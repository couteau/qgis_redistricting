"""QGIS Redistricting Plugin - unit tests for list classes

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

from collections.abc import Mapping, Sequence

import pytest

from redistricting.models.base import RdsBaseModel
from redistricting.models.lists import KeyedList, SortedKeyedList
from redistricting.models.serialization import deserialize, serialize

# ruff: noqa: E741


class UnkeyedModel(RdsBaseModel):
    name: str
    value: int


class ItemModel(UnkeyedModel):
    def __key__(self):
        return self.name


class TestKeyedList:
    def test_construct(self):
        l = KeyedList("key")
        assert len(l) == 0
        assert isinstance(l, Sequence)
        assert isinstance(l, Mapping)

    def test_construct_with_list(self):
        l = [ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)]

        kl = KeyedList[ItemModel](l)
        assert len(kl) == 3
        assert kl[0] is l[0]
        assert kl["A"] is l[0]
        assert kl[0].name == "A"

    def test_construct_with_dict(self):
        l = {"A": ItemModel("A", 0), "B": ItemModel("B", 1), "C": ItemModel("C", 2)}
        kl = KeyedList(iterable=l, key=ItemModel)
        assert len(kl) == 3
        assert kl[0] is l["A"]
        assert kl["A"] is l["A"]
        assert kl[0].name == "A"

    def test_append_item_with_duplicate_key_raises_exception(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        with pytest.raises(KeyError):
            kl.append(ItemModel("A", 3))

    def test_insert_item_with_duplicate_key_raises_exception(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        with pytest.raises(KeyError):
            kl.insert(2, ItemModel("A", 3))

    def test_set_item_with_duplicate_key_raises_exception(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        with pytest.raises(KeyError):
            kl[1] = ItemModel("A", 3)

    def test_set_item_same_key_replaces_item(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        item = ItemModel("A", 3)
        assert len(kl) == 3
        assert kl[0] is not item
        kl[0] = item
        assert kl[0].value == 3
        assert len(kl) == 3

        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        item = ItemModel("A", 3)
        assert len(kl) == 3
        assert kl[0] is not item
        kl["A"] = item
        assert kl[0].value == 3
        assert len(kl) == 3

    def test_set_item_int_index_new_key_replaces_key_and_value(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        itemD = ItemModel("D", 3)
        kl[0] = itemD
        assert kl[0].name == "D"
        assert list(kl.keys()) == ["D", "B", "C"]

    def test_set_item_non_matching_key_raises_exception(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        itemD = ItemModel("D", 3)
        with pytest.raises(ValueError, match="Item key doesn't match index"):
            kl["E"] = itemD

    def test_set_item_new_key_appends(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        itemD = ItemModel("D", 3)
        kl["D"] = itemD
        assert len(kl) == 4
        assert kl[3] is itemD

    def test_del_removes_item(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        assert len(kl) == 3
        del kl[1]
        assert len(kl) == 2
        with pytest.raises(KeyError):
            kl["B"]  # pylint: disable=pointless-statement
        assert kl[1].name == "C"

    def test_remove_removes_item(self):
        l = [ItemModel("A", 0), itemB := ItemModel("B", 1), ItemModel("C", 2)]
        kl = KeyedList[ItemModel](iterable=l)
        assert len(kl) == 3
        kl.remove(itemB)
        assert len(kl) == 2
        with pytest.raises(KeyError):
            kl["B"]  # pylint: disable=pointless-statement
        assert kl[1].name == "C"

    def test_set_item_slice_removes_items(self):
        kl = KeyedList[ItemModel](
            iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2), ItemModel("D", 3), ItemModel("E", 4)]
        )

        assert len(kl) == 5
        kl[2:3] = []
        assert len(kl) == 4
        assert list(kl.keys()) == ["A", "B", "D", "E"]
        kl = KeyedList[ItemModel](
            iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2), ItemModel("D", 3), ItemModel("E", 4)]
        )

        assert len(kl) == 5
        kl[2:4] = []
        assert len(kl) == 3
        assert list(kl.keys()) == ["A", "B", "E"]

    def test_set_item_slice_replaces_items(self):
        kl = KeyedList[ItemModel](
            iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2), ItemModel("D", 3), ItemModel("E", 4)]
        )

        itemF = ItemModel("F", 5)
        assert len(kl) == 5
        kl[2:3] = [itemF]
        assert len(kl) == 5
        assert list(kl.keys()) == ["A", "B", "F", "D", "E"]

    def test_set_item_slice_larger_than_value_removes_and_replaces(self):
        kl = KeyedList[ItemModel](
            iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2), ItemModel("D", 3), ItemModel("E", 4)]
        )

        itemF = ItemModel("F", 5)
        assert len(kl) == 5
        kl[2:4] = [itemF]
        assert len(kl) == 4
        assert list(kl.keys()) == ["A", "B", "F", "E"]

    def test_set_item_slice_smaller_than_value_inserts_and_replaces(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        itemD = ItemModel("D", 3)
        itemE = ItemModel("E", 4)
        assert len(kl) == 3
        kl[1:2] = [itemD, itemE]
        assert len(kl) == 4
        assert list(kl.keys()) == ["A", "D", "E", "C"]

    def test_move_moves_item(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        assert kl[0].name == "A"
        assert kl[1].name == "B"
        assert kl[2].name == "C"
        assert list(kl.keys()) == ["A", "B", "C"]
        kl.move(2, 1)
        assert kl[0].name == "A"
        assert kl[1].name == "C"
        assert kl[2].name == "B"
        assert list(kl.keys()) == ["A", "C", "B"]

        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)])
        assert kl[0].name == "A"
        assert kl[1].name == "B"
        assert kl[2].name == "C"
        assert list(kl.keys()) == ["A", "B", "C"]
        kl.move(1, 2)
        assert kl[0].name == "A"
        assert kl[1].name == "C"
        assert kl[2].name == "B"
        assert list(kl.keys()) == ["A", "C", "B"]

    # sorted lists

    def test_construct_sorted_keyed_list(self):
        l = [ItemModel("B", 0), ItemModel("A", 1), ItemModel("C", 2)]

        kl = SortedKeyedList[ItemModel](iterable=l)
        assert kl[0] is l[1]
        assert list(kl.keys()) == ["A", "B", "C"]

    def test_sorted_list_set_item_int_raises_exception(self):
        l = [ItemModel("B", 0), ItemModel("A", 1), ItemModel("C", 2)]

        kl = SortedKeyedList[ItemModel](iterable=l)

        with pytest.raises(NotImplementedError):
            kl[0] = ItemModel("D", 4)

    def test_sorted_list_append_item_inserts_sorted(self):
        kl = SortedKeyedList[ItemModel](iterable=[ItemModel("B", 0), ItemModel("A", 1), ItemModel("D", 3)])
        assert list(kl.keys()) == ["A", "B", "D"]
        itemC = ItemModel("C", 100)
        kl.append(itemC)
        assert kl[2] is itemC
        assert list(kl.keys()) == ["A", "B", "C", "D"]

    # serialization

    @pytest.mark.parametrize("cls", [KeyedList, SortedKeyedList])
    def test_serialize(self, cls: type[KeyedList]):
        kl = cls(iterable={"A": ItemModel("A", 0), "B": ItemModel("B", 1), "C": ItemModel("C", 2)}, key=ItemModel)
        d = serialize(kl)
        assert isinstance(d, dict)
        assert len(d) == 3

    @pytest.mark.parametrize("cls", [KeyedList, SortedKeyedList])
    def test_deserialize(self, cls: type[KeyedList]):
        kl = deserialize(
            cls[ItemModel],
            {"A": {"name": "A", "value": 0}, "B": {"name": "B", "value": 1}, "C": {"name": "C", "value": 2}},
        )
        assert isinstance(kl, cls)
        assert len(kl) == 3
        assert isinstance(kl[0], ItemModel)
