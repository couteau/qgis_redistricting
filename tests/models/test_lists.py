
from typing import (
    Mapping,
    Sequence
)

import pytest

from redistricting.models.base import (
    KeyedList,
    RdsBaseModel,
    SortedKeyedList,
    deserialize,
    serialize
)


class UnkeyedModel(RdsBaseModel):
    name: str
    value: int


class ItemModel(UnkeyedModel):
    def __key__(self):
        return self.name


class TestKeyedList:
    def test_construct(self):
        l = KeyedList()
        assert len(l) == 0
        assert isinstance(l, Sequence)
        assert isinstance(l, Mapping)

    def test_construct_with_list(self):
        l = [ItemModel("A", 0), ItemModel("B", 1), ItemModel("C", 2)]

        kl = KeyedList[ItemModel](iterable=l)
        assert len(kl) == 3
        assert kl[0] is l[0]
        assert kl["A"] is l[0]
        assert kl[0].name == "A"

    def test_construct_with_dict(self):
        l = {"A": ItemModel("A", 0), "B": ItemModel("B", 1), "C": ItemModel("C", 2)}
        kl = KeyedList(iterable=l)
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
        with pytest.raises(ValueError):
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
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel(
            "B", 1), ItemModel("C", 2), ItemModel("D", 3), ItemModel("E", 4)])

        assert len(kl) == 5
        kl[2:3] = []
        assert len(kl) == 4
        assert list(kl.keys()) == ["A", "B", "D", "E"]
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel(
            "B", 1), ItemModel("C", 2), ItemModel("D", 3), ItemModel("E", 4)])

        assert len(kl) == 5
        kl[2:4] = []
        assert len(kl) == 3
        assert list(kl.keys()) == ["A", "B", "E"]

    def test_set_item_slice_replaces_items(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel(
            "B", 1), ItemModel("C", 2), ItemModel("D", 3), ItemModel("E", 4)])

        itemF = ItemModel("F", 5)
        assert len(kl) == 5
        kl[2:3] = [itemF]
        assert len(kl) == 5
        assert list(kl.keys()) == ["A", "B", "F", "D", "E"]

    def test_set_item_slice_larger_than_value_removes_and_replaces(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel(
            "B", 1), ItemModel("C", 2), ItemModel("D", 3), ItemModel("E", 4)])

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

    def test_set_item_slice_with_dict_value_and_non_matching_key_raises_exception(self):
        kl = KeyedList[ItemModel](iterable=[ItemModel("A", 0), ItemModel(
            "Z", 1), ItemModel("Y", 2), ItemModel("B", 3), ItemModel("C", 4)])

        itemD = ItemModel("D", 42)
        itemE = ItemModel("E", 100)
        itemF = ItemModel("F", 100)

        with pytest.raises(ValueError):
            kl[2:5] = {"N": itemD, "O": itemE, "F": itemF}
        assert list(kl.keys()) == ["A", "Z", "Y", "B", "C"]

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

    # unkeyed items

    def test_construct_with_dict_of_unkeyed_items(self):
        l = {"X": UnkeyedModel("A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)}
        kl = KeyedList(iterable=l)
        assert len(kl) == 3
        assert kl[0] is l["X"]
        assert kl["X"] is l["X"]
        assert kl["X"].name == "A"

    def test_remove_unkeyed_item_removes_item(self):
        itemB = UnkeyedModel("B", 1)
        l = {"A": UnkeyedModel("A", 0), "B": itemB, "C": UnkeyedModel("C", 2)}
        kl = KeyedList(iterable=l)
        kl.remove(itemB)
        assert len(kl) == 2
        with pytest.raises(KeyError):
            kl["B"]  # pylint: disable=pointless-statement
        assert kl[1].name == "C"

    def test_set_unkeyeditem_int_index_replaces(self):
        kl = KeyedList(iterable={"X": UnkeyedModel("A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)})
        itemD = UnkeyedModel("D", 100)
        kl[1] = itemD
        assert len(kl) == 3
        assert kl[1] is itemD
        assert kl["Y"] is itemD

    def test_append_unkeyeditem_raises_exception(self):
        kl = KeyedList(iterable={"X": UnkeyedModel("A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)})
        itemD = UnkeyedModel("D", 100)
        with pytest.raises(ValueError):
            kl.append(itemD)

    def test_insert_unkeyeditem_raises_exception(self):
        kl = KeyedList(iterable={"X": UnkeyedModel("A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)})
        itemD = UnkeyedModel("D", 100)
        with pytest.raises(ValueError):
            kl.insert(1, itemD)

    def test_set_unkeyeditem_new_key_appends(self):
        kl = KeyedList(iterable={"X": UnkeyedModel("A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)})
        itemD = UnkeyedModel("D", 100)
        kl["W"] = itemD
        assert len(kl) == 4
        assert kl[3] is itemD
        assert list(kl.keys())[3] == "W"

    def test_set_unkeyeditem_slice_replaces_items(self):
        kl = KeyedList(iterable={"X": UnkeyedModel("A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)})
        itemD = UnkeyedModel("D", 100)
        kl[1:2] = [itemD]
        assert list(kl.keys()) == ["X", "Y", "Z"]
        assert kl[1] is itemD

    def test_set_unkeyeditem_slice_larger_removes_replaces_items(self):
        kl = KeyedList(iterable={"W": UnkeyedModel("N", 42), "X": UnkeyedModel(
            "A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)})
        itemD = UnkeyedModel("D", 100)
        kl[1:3] = [itemD]
        assert list(kl.keys()) == ["W", "X", "Z"]
        assert kl[1] is itemD

    def test_set_unkeyeditem_slice_with_dict_value_replaces_keys_and_values(self):
        itemN = UnkeyedModel("N", 42)
        itemC = UnkeyedModel("C", 2)
        kl = KeyedList(iterable={"W": itemN, "X": UnkeyedModel(
            "A", 0), "Y": UnkeyedModel("B", 1), "Z": itemC})
        itemD = UnkeyedModel("D", 100)
        itemE = UnkeyedModel("E", 101)
        kl[1:3] = {"A": itemD, "B": itemE}
        assert list(kl.keys()) == ["W", "A", "B", "Z"]
        assert kl[0] is itemN
        assert kl[1] is itemD
        assert kl[2] is itemE
        assert kl[3] is itemC

    def test_extend_unkeyed_items_from_dict_extends_list(self):
        kl = KeyedList(iterable={"X": UnkeyedModel("A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)})
        itemD = UnkeyedModel("D", 100)
        kl.extend({"W": itemD})
        assert len(kl) == 4
        assert kl[3] is itemD
        assert list(kl.keys())[3] == "W"

    def test_extend_unkeyed_items_from_list_raises_exception(self):
        kl = KeyedList(iterable={"X": UnkeyedModel("A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)})
        itemD = UnkeyedModel("D", 100)
        with pytest.raises(ValueError):
            kl.extend([itemD])

    def test_move_unkeyed_moves_item(self):
        kl = KeyedList(iterable={"X": UnkeyedModel("A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)})
        assert kl[0].name == "A"
        assert kl[1].name == "B"
        assert kl[2].name == "C"
        assert list(kl.keys()) == ["X", "Y", "Z"]
        kl.move(2, 1)
        assert kl[0].name == "A"
        assert kl[1].name == "C"
        assert kl[2].name == "B"
        assert list(kl.keys()) == ["X", "Z", "Y"]

        kl = KeyedList(iterable={"X": UnkeyedModel("A", 0), "Y": UnkeyedModel("B", 1), "Z": UnkeyedModel("C", 2)})
        assert kl[0].name == "A"
        assert kl[1].name == "B"
        assert kl[2].name == "C"
        assert list(kl.keys()) == ["X", "Y", "Z"]
        kl.move(1, 2)
        assert kl[0].name == "A"
        assert kl[1].name == "C"
        assert kl[2].name == "B"
        assert list(kl.keys()) == ["X", "Z", "Y"]

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
        kl = cls(iterable={"A": ItemModel("A", 0), "B": ItemModel("B", 1), "C": ItemModel("C", 2)})
        d = serialize(kl)
        assert isinstance(d, dict)
        assert len(d) == 3

    @pytest.mark.parametrize("cls", [KeyedList, SortedKeyedList])
    def test_deserialize(self, cls: type[KeyedList]):
        kl = deserialize(cls[ItemModel], {
            'A': {'name': 'A', 'value': 0},
            'B': {'name': 'B', 'value': 1},
            'C': {'name': 'C', 'value': 2}
        })
        assert isinstance(kl, cls)
        assert len(kl) == 3
        assert isinstance(kl[0], ItemModel)
