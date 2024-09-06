from typing import (
    Annotated,
    Union
)

import pytest
from qgis.PyQt.QtCore import QObject

from redistricting.models.base import (
    Factory,
    RdsBaseModel,
    deserialize,
    get_real_type,
    in_range,
    not_empty,
    rds_property,
    serialize
)

# pylint: disable=redefined-outer-name, unused-argument, protected-access


class TestBaseModel:
    class ModelTest(RdsBaseModel):
        prop1: str = "default"
        prop2: int = 1

    def test_init(self):
        inst = TestBaseModel.ModelTest()
        assert inst.prop1 == "default"
        assert inst.prop2 == 1

    def test_repr(self):
        inst = TestBaseModel.ModelTest()
        assert repr(inst) == "ModelTest(prop1='default', prop2=1)"

    def test_serialize(self):
        inst = TestBaseModel.ModelTest()
        data = serialize(inst)
        assert data == {"prop1": "default", "prop2": 1}

    def test_deserialize(self):
        data = {"prop1": "string", "prop2": -1}
        inst = deserialize(TestBaseModel.ModelTest, data)
        assert inst.prop1 == "string"
        assert inst.prop2 == -1

    def test_deserialize_with_parent(self):
        parent = QObject()
        data = {"prop1": "string", "prop2": -1}
        inst = deserialize(TestBaseModel.ModelTest, data, parent=parent)
        assert inst.prop1 == "string"
        assert inst.prop2 == -1
        assert inst.parent() == parent

    def test_init_with_init(self):
        class ModelTest2(RdsBaseModel):
            prop1: str = "default"
            prop2: int = 1

        inst = ModelTest2("string", -1, None)
        assert inst.prop1 == "string"
        assert inst.prop2 == -1

    def test_deserialize_with_init(self):
        class ModelTest3(RdsBaseModel):
            prop1: str = "default"
            prop2: int = 1

        inst = deserialize(ModelTest3, {"prop1": "string", "prop2": -1})
        assert inst.prop1 == "string"
        assert inst.prop2 == -1

    def test_deserialize_with_no_default(self):
        class ModelTest4(RdsBaseModel):
            prop1: str
            prop2: int = -1

        inst = deserialize(ModelTest4, {"prop1": "value"})
        assert inst.prop1 == "value"
        assert inst.prop2 == -1

    def test_serialize_with_list(self):
        class ModelTest5(RdsBaseModel):
            prop1: str = "default"
            prop2: list[int] = [1]

        inst = ModelTest5()
        data = serialize(inst)
        assert data == {"prop1": "default", "prop2": [1]}

    def test_deserialize_with_list(self):
        class ModelTest6(RdsBaseModel):
            prop1: str = "default"
            prop2: list[int] = [1]

        inst = deserialize(ModelTest6, {"prop1": "string", "prop2": [-1]})
        assert inst.prop1 == "string"
        assert inst.prop2 == [-1]

    def test_base_model(self):
        def factory():
            return []

        class Owned:
            def __init__(self, p: 'ModelTest7'):
                ...

        class ModelTest7(RdsBaseModel):
            field1: str
            field2: int = rds_property(private=True, default=-1)
            field3: list = rds_property(private=True, factory=list)
            field4: list = rds_property(private=True, factory=factory)
            field5: Owned = Factory(Owned)

        c = ModelTest7(field1="test")
        assert c.field1 == "test"
        assert c.field2 == -1
        assert c.field3 == []
        assert c.field4 == []
        assert isinstance(c.field5, Owned)

        parent = QObject()

        c = ModelTest7(field1="Test2", parent=parent)
        assert c.parent() is parent

        c = ModelTest7("Test3", parent=parent)
        assert c.field1 == "Test3"
        assert c.field2 == -1
        assert c.field3 == []
        assert c.field4 == []
        assert isinstance(c.field5, Owned)
        assert c.parent() is parent

        c = ModelTest7("Test4", 10, ['a'], [2], None, parent)
        assert c.field1 == "Test4"
        assert c.field2 == 10
        assert c.field3 == ['a']
        assert c.field4 == [2]
        assert c.field5 is None
        assert c.parent() is parent

    @pytest.mark.parametrize('minmax,value', [
        [(1, 5), 7],
        [('a', 'd'), 'e']
    ])
    def test_range_outofrange_raises_valueerror(self, minmax, value):
        r = in_range(*minmax)
        with pytest.raises(ValueError):
            r(None, value)

    @pytest.mark.parametrize('minmax,value', [
        [(1, 2), 'a'],
        [('a', 'z'), 1]
    ])
    def test_range_incompatible_types_raises_typeerror(self, minmax, value):
        r = in_range(*minmax)
        with pytest.raises(TypeError):
            r(None, value)


class TestRdsProperty:
    def test_get_real_type_annotated_single_type(self):
        t, v = get_real_type(Annotated[int, "validator"])
        assert t is int
        assert v == "validator"

    def test_get_real_type_annotated_union_type(self):
        t, v = get_real_type(Annotated[Union[int, str], "validator"])
        assert t is Union[int, str]
        assert v == "validator"

    def test_get_real_type_annotated_list_returns_annotated_list(self):
        t, v = get_real_type(list[str])
        assert t == list
        assert v is None

    def test_not_empty_validator(self):
        t = not_empty(None, "name")
        assert t == "name"
        with pytest.raises(ValueError):
            t = not_empty(None, "")

        t = not_empty()
        with pytest.raises(ValueError):
            t(None, "")

        assert t(None, "name") == "name"
