"""QGIS Redistricting Plugin - unit tests for RdsField class

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
from pytestqt.qtbot import QtBot
from qgis.core import QgsField
from qgis.PyQt.QtCore import QVariant

from redistricting.models import RdsDataField, RdsField, RdsGeoField, RdsRelatedField
from redistricting.models.base.serialization import deserialize, serialize

# pylint: disable=comparison-with-callable, protected-access, unused-argument


class TestField:
    @pytest.fixture
    def field(self, block_layer) -> RdsField:
        return RdsField(block_layer, "vtdid")

    @pytest.fixture
    def expr(self, block_layer) -> RdsField:
        return RdsField(block_layer, "statefp || countyfp || tractce")

    def test_create(self, block_layer):
        field = RdsField(block_layer, "vtdid")
        assert field.field == "vtdid"
        assert field.expression.isField()
        assert field.caption == "vtdid"

        field = RdsField(block_layer, "pop_total", "Total Pop.")
        assert field.field == "pop_total"
        assert field.layer == block_layer
        assert field.caption == "Total Pop."  # pylint: disable=W0143
        assert field.isValid()

    def test_invalid_field(self, block_layer):
        f = RdsField(block_layer, "foo_total", "Total Foo.")
        assert f.field == "foo_total"
        assert f.layer == block_layer
        assert not f.isValid()
        assert f.errors() == ["Field 'foo_total' not found"]

    def test_invalid_expr(self, block_layer):
        f = RdsField(block_layer, "not_a_field + still_not")
        assert not f.isValid()

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

        field = RdsField(block_layer, "statefp || countyfp || tractce")
        assert field.isValid()
        assert field.field == "statefp || countyfp || tractce"
        assert field.caption == "statefp || countyfp || tractce"
        assert field.fieldName == "statefp_countyfp_tractce"

    def test_create_withcaption(self, block_layer):
        field = RdsField(block_layer, "vtdid", caption="VTD")
        assert field.field == "vtdid"
        assert field.caption == "VTD"

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

    def test_getvalue_field(self, block_layer, field):
        f = next(block_layer.getFeatures())
        v = field.getValue(f)
        assert not field.errors()
        assert isinstance(v, str)
        assert len(v) == 11

    def test_prepare_field(self, block_layer):
        f = RdsField(block_layer, "pop_total")
        feat = block_layer.getFeature(747)
        f.prepare()
        assert f._prepared
        assert f._context is not None
        assert f.getValue(feat) == 115

    def test_getvalue_expr(self, block_layer, expr):
        f = next(block_layer.getFeatures())
        v = expr.getValue(f)
        assert not expr.errors()
        assert isinstance(v, str)
        assert len(v) == 11

    def test_prepare_expr(self, block_layer):
        f = RdsField(block_layer, "pop_black/pop_total")
        feat = block_layer.getFeature(759)
        f.prepare()
        assert f._prepared
        assert f._context is not None
        assert f.getValue(feat) == 1 / 3

    def test_makeqgsfield_field(self, field):
        qf = field.makeQgsField()
        assert qf.type() == QVariant.String

    def test_makeqgsfield_expr(self, expr):
        qf = expr.makeQgsField()
        assert qf.type() == QVariant.String

    def test_serialize(self, block_layer, field: RdsField):
        data = serialize(field)
        assert data == {"layer": block_layer.id(), "field": "vtdid", "caption": "vtdid", "category": 1}

    def test_deserialize(self, block_layer):
        data = {"layer": block_layer.id(), "field": "vtdid"}
        field = deserialize(RdsField, data)
        assert field.field == "vtdid"
        assert field.layer == block_layer
        assert field.caption == "vtdid"


class TestGeoField:
    def test_geo_field(self, block_layer, vtd_layer, related_layers):
        vtd_name = RdsRelatedField(vtd_layer, "name")
        assert vtd_name.isValid()
        f = RdsGeoField(block_layer, "vtdid", nameField=vtd_name)
        assert f.isValid()

    def test_geo_field_no_namefield_sets_default_namefield(self, block_layer, vtd_layer, related_layers):
        f = RdsGeoField(block_layer, "vtdid")
        assert f.nameField is not None
        assert f.nameField.layer == vtd_layer
        assert f.nameField.field == "name"

    def test_get_name(self, block_layer, vtd_layer, related_layers):
        vtd_name = RdsRelatedField(vtd_layer, "name")
        f = RdsGeoField(block_layer, "vtdid", nameField=vtd_name)
        feat = block_layer.getFeature(746)
        f.prepare()
        assert f.getValue(feat) == "01125000021"
        vtd_name.prepare()
        assert f.getName(feat) == "Northport City Hall"

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


class TestDataField:
    @pytest.fixture
    def data_field(self, block_layer) -> RdsDataField:
        return RdsDataField(block_layer, "vap_ap_black", pctBase="vap_total")

    @pytest.fixture
    def data_field_expr(self, block_layer) -> RdsDataField:
        return RdsDataField(
            block_layer,
            "vap_nh_ap_black + vap_nh_asian + vap_nh_aiakn + vap_hispanic",
            caption="Dream Team",
            pctBase="vap_total",
        )

    def test_create(self, block_layer):
        field = RdsDataField(block_layer, "vap_ap_black", pctBase="vap_total")
        assert field.field == "vap_ap_black"
        assert field.sumField
        assert field.pctBase == "vap_total"

    def test_create_expr(self, block_layer):
        field = RdsDataField(block_layer, "vap_nh_ap_black + vap_hispanic")
        assert field.field == "vap_nh_ap_black + vap_hispanic"
        assert field.sumField
        assert field.pctBase is None

    def test_serialize(self, block_layer, data_field):
        data = serialize(data_field)
        assert data == {
            "layer": block_layer.id(),
            "field": "vap_ap_black",
            "caption": "vap_ap_black",
            "category": 3,
            "sum-field": True,
            "pct-base": "vap_total",
        }

    def test_deserialize(self, block_layer):
        data = {"layer": block_layer.id(), "field": "vap_ap_black", "caption": "APBVAP", "pct-base": "vap_total"}
        field = deserialize(RdsDataField, data)
        assert field.field == "vap_ap_black"
        assert field.layer == block_layer
        assert field.caption == "APBVAP"
        assert field.sumField  # pylint: disable=no-member
        assert field.pctBase == "vap_total"  # pylint: disable=no-member

    def test_makeqgsfield_field(self, data_field):
        qf = data_field.makeQgsField()
        assert qf.type() == QVariant.LongLong

    def test_makeqgsfield_field_expr(self, data_field_expr):
        qf = data_field_expr.makeQgsField()
        assert isinstance(qf, QgsField)
        assert qf.type() == QVariant.Int
