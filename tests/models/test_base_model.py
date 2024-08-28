from typing import (
    Annotated,
    Union
)

import pytest
from pytestqt.qtbot import QtBot
from qgis.PyQt.QtCore import QObject

from redistricting.models import (
    RdsDataField,
    RdsField,
    RdsGeoField,
    RdsPlan
)
from redistricting.models.base import (
    Factory,
    RdsBaseModel,
    deserialize_model,
    get_real_type,
    in_range,
    not_empty,
    rds_property,
    serialize_model
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
        data = serialize_model(inst)
        assert data == {"prop1": "default", "prop2": 1}

    def test_deserialize(self):
        data = {"prop1": "string", "prop2": -1}
        inst = deserialize_model(TestBaseModel.ModelTest, data)
        assert inst.prop1 == "string"
        assert inst.prop2 == -1

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

        inst = deserialize_model(ModelTest3, {"prop1": "string", "prop2": -1}, None)
        assert inst.prop1 == "string"
        assert inst.prop2 == -1

    def test_deserialize_with_no_default(self):
        class ModelTest4(RdsBaseModel):
            prop1: str
            prop2: int = -1

        inst = deserialize_model(ModelTest4, {"prop1": "value"}, None)
        assert inst.prop1 == "value"
        assert inst.prop2 == -1

    def test_serialize_with_list(self):
        class ModelTest5(RdsBaseModel):
            prop1: str = "default"
            prop2: list[int] = [1]

        inst = ModelTest5()
        data = serialize_model(inst)
        assert data == {"prop1": "default", "prop2": [1]}

    def test_deserialize_with_list(self):
        class ModelTest6(RdsBaseModel):
            prop1: str = "default"
            prop2: list[int] = [1]

        inst = deserialize_model(ModelTest6, {"prop1": "string", "prop2": [-1]}, None)
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


class TestNewFieldModel:
    def test_field(self, block_layer):
        f = RdsField(block_layer, "pop_total", "Total Pop.")
        assert f.field == "pop_total"
        assert f.layer == block_layer
        assert f.caption == "Total Pop."  # pylint: disable=W0143
        assert f.isValid()

    def test_invalid_field(self, block_layer):
        f = RdsField(block_layer, "foo_total", "Total Foo.")
        assert f.field == "foo_total"
        assert f.layer == block_layer
        assert not f.isValid()
        assert f.errors() == ["Field 'foo_total' not found"]

    def test_no_layer_raises_error(self):
        with pytest.raises(TypeError):
            RdsField("pop_total")

    def test_default_caption_field(self, block_layer):
        f = RdsField(block_layer, "pop_total")
        assert f.caption == "pop_total"  # pylint: disable=W0143

    def test_expression(self, block_layer):
        f = RdsField(block_layer, "pop_black/pop_total")
        assert f.field == "pop_black/pop_total"
        assert f.isValid()

    def test_fieldname_expression(self, block_layer):
        f = RdsField(block_layer, "pop_black/pop_total")
        assert f.fieldName == "pop_black_pop_total"  # pylint: disable=W0143

    def test_set_caption(self, block_layer):
        f = RdsField(block_layer, "pop_total")
        assert f.caption == "pop_total"
        f.caption = "Total Pop."
        assert f.caption == "Total Pop."

    def test_set_caption_signals(self, block_layer, qtbot: QtBot):
        f = RdsField(block_layer, "pop_total")
        with qtbot.waitSignal(f.captionChanged):
            f.caption = "Total Pop."

    def test_get_value(self, block_layer):
        f = RdsField(block_layer, "pop_total")
        feat = block_layer.getFeature(747)
        f.prepare()
        assert f.getValue(feat) == 115

    def test_get_value_expression(self, block_layer):
        f = RdsField(block_layer, "pop_black/pop_total")
        feat = block_layer.getFeature(759)
        f.prepare()
        assert f.getValue(feat) == 1/3

    def test_geo_field(self, block_layer, vtd_layer, related_layers):
        vtd_name = RdsField(vtd_layer, "name")
        assert vtd_name.isValid()
        f = RdsGeoField(block_layer, "vtdid", nameField=vtd_name)
        assert f.isValid()

    def test_geo_field_no_namefield_sets_default_namefield(self, block_layer, vtd_layer, related_layers):
        f = RdsGeoField(block_layer, "vtdid")
        assert f.nameField is not None
        assert f.nameField.layer == vtd_layer
        assert f.nameField.field == "name"

    def test_get_name(self, block_layer, vtd_layer, related_layers):
        vtd_name = RdsField(vtd_layer, "name")
        f = RdsGeoField(block_layer, "vtdid", nameField=vtd_name)
        feat = block_layer.getFeature(746)
        f.prepare()
        assert f.getValue(feat) == '01125000021'
        vtd_name.prepare()
        assert f.getName(feat) == 'Northport City Hall'

    def test_data_field(self, block_layer):
        f = RdsDataField(block_layer, "pop_black")
        assert f.sumField
        assert f.pctBase is None

    def test_data_field_str_sets_sumfield_false(self, block_layer):
        f = RdsDataField(block_layer, "vtdid")
        assert not f.sumField
        assert f.pctBase is None

    def test_data_field_str_set_sumfield_true_nochange(self, block_layer):
        f = RdsDataField(block_layer, "vtdid")
        f.sumField = True
        assert not f.sumField

    def test_data_field_str_set_pctbase_str_nochange(self, block_layer):
        f = RdsDataField(block_layer, "vtdid")
        f.pctBase = "pop_total"
        assert f.pctBase is None

    def test_data_field_set_summary_fields_signal(self, block_layer, qtbot: QtBot):
        f = RdsDataField(block_layer, "pop_black", sumField=False)
        assert not f.sumField
        with qtbot.waitSignal(f.sumFieldChanged):
            f.sumField = True
        assert f.sumField

        with qtbot.waitSignal(f.sumFieldChanged):
            f.sumField = False
        assert not f.sumField

        assert f.pctBase is None
        with qtbot.waitSignal(f.pctBaseChanged):
            f.pctBase = "pop_total"
        assert f.pctBase == "pop_total"

        with qtbot.waitSignal(f.pctBaseChanged):
            f.pctBase = None
        assert f.pctBase is None

    def test_data_field_str_set_summary_fields_nosignal(self, block_layer, qtbot: QtBot):
        f = RdsDataField(block_layer, "vtdid")
        with qtbot.assertNotEmitted(f.sumFieldChanged):
            f.sumField = True

        with qtbot.assertNotEmitted(f.pctBaseChanged):
            f.pctBase = "pop_total"


class TestNewPlan:
    def test_create_plan(self):
        p = RdsPlan("test", 5)
        assert p.name == "test"
        assert p.numDistricts == 5
        assert p.numSeats == 5

    def test_create_invalid_name_raises_value_error(self):
        with pytest.raises(ValueError):
            RdsPlan("", 5)

    def test_create_invalid_numdistricts_raises_value_error(self):
        with pytest.raises(ValueError):
            RdsPlan("test", 1)

    def test_set_invalid_numdistricts_raises_value_error(self):
        p = RdsPlan("test", 5)
        with pytest.raises(ValueError):
            p.numDistricts = 1
