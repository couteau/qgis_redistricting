"""QGIS Redistricting Plugin - unit tests for model classes

Copyright (C) 2022-2024, Stuart C. Naifeh

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

from typing import Annotated, Union

import pytest
from qgis.PyQt.QtCore import QObject

from redistricting.models.base.model import Factory, RdsBaseModel
from redistricting.models.base.prop import field, get_real_type, in_range, not_empty, rds_property
from redistricting.models.base.serialization import deserialize, serialize

# pylint: disable=redefined-outer-name, unused-argument, protected-access


class TestBaseModel:
    class ModelTest(RdsBaseModel):
        prop1: str = "default"
        prop2: int = 1

    def test_base_model(self):
        class M(RdsBaseModel):
            f1: str
            f2: int = field(default=1)
            f3: float = rds_property(private=True, readonly=True, default=0.0)
            f4: list[int] = rds_property(private=True, factory=list)

        assert M.f3.fset is None
        assert M.f3.finit is not None

        m = M(f1="dummy")
        assert m.f1 == "dummy"
        assert m.f2 == 1
        assert m.f3 == 0.0
        assert m.f4 == []  # pylint: disable=C1803, W0143
        assert hasattr(m, "_f3")

        l = m.f4
        m.f4 = [1]

        assert l == [1]
        assert l is m.f4

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

    def test_base_model_with_factory(self):
        def factory():
            return []

        class Owned:
            def __init__(self, p: "ModelTest7"):
                self.owner = p

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
        assert c.field5.owner == c  # pylint: disable=no-member

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

        c = ModelTest7("Test4", 10, ["a"], [2], None, parent)
        assert c.field1 == "Test4"
        assert c.field2 == 10
        assert c.field3 == ["a"]
        assert c.field4 == [2]
        assert c.field5 is None
        assert c.parent() is parent

    @pytest.mark.parametrize(("minmax", "value"), [((1, 5), 7), (("a", "d"), "e")])
    def test_range_outofrange_raises_valueerror(self, minmax, value):
        r = in_range(*minmax)
        with pytest.raises(ValueError, match="Value must be between"):
            r(None, value)

    @pytest.mark.parametrize(("minmax", "value"), [((1, 2), "a"), (("a", "z"), 1)])
    def test_range_incompatible_types_raises_typeerror(self, minmax, value):
        r = in_range(*minmax)
        with pytest.raises(TypeError, match="Range and value are incompatible types"):
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
        assert t is list
        assert v is None

    def test_not_empty_validator(self):
        t = not_empty(None, "name")
        assert t == "name"
        with pytest.raises(ValueError, match="Value must not be empty"):
            t = not_empty(None, "")

        t = not_empty()
        with pytest.raises(ValueError, match="Value must not be empty"):
            t(None, "")

        assert t(None, "name") == "name"

    def test_rds_property(self):
        class C:
            prop: str = ""

            def get_prop(self):
                """Docstring"""
                return self.prop

            def set_prop(self, value):
                self.prop = value

            def del_prop(self):
                del self.__dict__["prop"]

            def valid_prop(self, value):
                if len(value) > 10:
                    raise ValueError()

        p = rds_property(C.get_prop)
        p = p.setter(C.set_prop)
        p = p.deleter(C.del_prop)
        p = p.validator(C.valid_prop)

        assert p.fget == C.get_prop
        assert p.fset == C.set_prop
        assert p.fdel == C.del_prop
        assert p.fvalid == C.valid_prop
        assert p.__doc__ == "Docstring"

    def test_rds_property_decorator(self):
        class C:
            prop: str = ""

            @rds_property
            def my_prop(self):
                """Docstring"""
                return self.prop

            @my_prop.setter
            def my_prop(self, value):
                self.prop = value

            @my_prop.deleter
            def my_prop(self):
                del self.__dict__["prop"]

            @my_prop.validator
            def my_prop(self, value):
                if len(value) > 10:
                    raise ValueError()

        # pylint: disable=no-member
        assert callable(C.my_prop.fget)
        assert callable(C.my_prop.fset)
        assert callable(C.my_prop.fdel)
        assert callable(C.my_prop.fvalid)
        assert C.my_prop.__doc__ == "Docstring"

    def test_rds_property_private(self):
        class C:
            my_prop: str = rds_property(private=True)

        assert C.my_prop.fset == C.my_prop.set_private

        class D:
            my_prop: list[str]

            @rds_property(private=True)
            def my_prop(self) -> list[str]:
                return self._my_prop  # pylint: disable=no-member

            @my_prop.validator
            def my_prop(self, value: list) -> list[str]:
                assert all(isinstance(p, str) for p in value)
                return value

        assert D.my_prop.fset == D.my_prop.set_list  # pylint: disable=no-member
