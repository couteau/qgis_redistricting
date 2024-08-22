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
from qgis.core import QgsField
from qgis.PyQt.QtCore import QVariant

from redistricting.models import (
    RdsDataField,
    RdsField
)
from redistricting.models.serialize import (
    deserialize_model,
    serialize_model
)

# pylint: disable=comparison-with-callable


class TestField:
    @pytest.fixture
    def field(self, block_layer) -> RdsField:
        return RdsField(block_layer, 'vtdid')

    @pytest.fixture
    def expr(self, block_layer) -> RdsField:
        return RdsField(block_layer, 'statefp || countyfp || tractce')

    def test_create(self, block_layer):
        field = RdsField(block_layer, 'vtdid')
        assert field.field == 'vtdid'
        assert field.expression.isField()
        assert field.caption == 'vtdid'

    def test_create_expr(self, block_layer):
        field = RdsField(block_layer, 'statefp || countyfp || tractce')
        assert field.field == 'statefp || countyfp || tractce'
        assert field.caption == 'statefp || countyfp || tractce'
        assert field.fieldName == 'statefp_countyfp_tractce'

    def test_create_withcaption(self, block_layer):
        field = RdsField(block_layer, 'vtdid', caption='VTD')
        assert field.field == 'vtdid'
        assert field.caption == 'VTD'

    def test_bad_field(self, block_layer):
        f = RdsField(block_layer, 'not_a_field')
        assert not f.isValid()

    def test_bad_expr(self, block_layer):
        f = RdsField(block_layer, 'not_a_field + still_not')
        assert not f.isValid()

    def test_getvalue_field(self, block_layer, field):
        f = next(block_layer.getFeatures())
        v = field.getValue(f)
        assert not field.errors() and isinstance(v, str) and len(v) == 11

    def test_getvalue_expr(self, block_layer, expr):
        f = next(block_layer.getFeatures())
        v = expr.getValue(f)
        assert not expr.errors()
        assert isinstance(v, str)
        assert len(v) == 11

    def test_makeqgsfield_field(self, field):
        qf = field.makeQgsField()
        assert qf.type() == QVariant.String

    def test_makeqgsfield_expr(self, expr):
        qf = expr.makeQgsField()
        assert qf.type() == QVariant.String

    def test_serialize(self, block_layer, field: RdsField):
        data = serialize_model(field)
        assert data == {'layer': block_layer.id(),
                        'field': 'vtdid',
                        'caption': 'vtdid'}

    def test_deserialize(self, block_layer):
        data = {'layer': block_layer.id(), 'field': 'vtdid'}
        field = deserialize_model(RdsField, data)
        assert field.field == 'vtdid'
        assert field.layer == block_layer
        assert field.caption == 'vtdid'


class TestDataField:
    @pytest.fixture
    def data_field(self, block_layer) -> RdsDataField:
        return RdsDataField(block_layer, 'vap_ap_black', pctBase='vap_total')

    @pytest.fixture
    def data_field_expr(self, block_layer) -> RdsDataField:
        return RdsDataField(
            block_layer,
            'vap_nh_ap_black + vap_nh_asian + vap_nh_aiakn + vap_hispanic',
            caption='Dream Team',
            pctBase='vap_total'
        )

    def test_create(self, block_layer):
        field = RdsDataField(block_layer, 'vap_ap_black', pctBase='vap_total')
        assert field.field == 'vap_ap_black' and field.sumField and field.pctBase == 'vap_total'

    def test_create_expr(self, block_layer):
        field = RdsDataField(block_layer, 'vap_nh_ap_black + vap_hispanic')
        assert field.field == 'vap_nh_ap_black + vap_hispanic' and field.sumField and field.pctBase is None

    def test_serialize(self, block_layer, data_field):
        data = serialize_model(data_field)
        assert data == {
            'layer': block_layer.id(),
            'field': 'vap_ap_black',
            'caption': 'vap_ap_black',
            'sum-field': True,
            'pct-base': 'vap_total'
        }

    def test_deserialize(self, block_layer):
        data = {
            'layer': block_layer.id(),
            'field': 'vap_ap_black',
            'caption': 'APBVAP',
            'pct-base': 'vap_total'
        }
        field = deserialize_model(RdsDataField, data)
        assert field.field == 'vap_ap_black'
        assert field.layer == block_layer
        assert field.caption == 'APBVAP'
        assert field.sumField  # pylint: disable=no-member
        assert field.pctBase == 'vap_total'  # pylint: disable=no-member

    def test_makeqgsfield_field(self, data_field):
        qf = data_field.makeQgsField()
        assert qf.type() == QVariant.LongLong

    def test_makeqgsfield_field_expr(self, data_field_expr):
        qf = data_field_expr.makeQgsField()
        assert isinstance(qf, QgsField)
        assert qf.type() == QVariant.Int
