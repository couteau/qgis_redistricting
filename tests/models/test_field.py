"""QGIS Redistricting Plugin - unit tests for Field class

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
from qgis.PyQt.QtCore import QVariant

from redistricting.models import (
    DataField,
    Field
)


class TestField:
    @pytest.fixture
    def field(self, block_layer) -> Field:
        return Field(block_layer, 'vtdid')

    @pytest.fixture
    def expr(self, block_layer) -> Field:
        return Field(block_layer, 'statefp || countyfp || tractce')

    def test_create(self, block_layer):
        field = Field(block_layer, 'vtdid')
        assert field.field == 'vtdid'
        assert not field.isExpression
        assert field.caption == 'vtdid'

    def test_create_expr(self, block_layer):
        field = Field(block_layer, 'statefp || countyfp || tractce')
        assert field.field == 'statefp || countyfp || tractce'
        assert field.isExpression
        assert field.caption == 'statefp || countyfp || tractce'
        assert field.fieldName == 'statefp_countyfp_tractce'

    def test_create_withcaption(self, block_layer):
        field = Field(block_layer, 'vtdid', caption='VTD')
        assert field.field == 'vtdid'
        assert not field.isExpression
        assert field.caption == 'VTD'

    def test_bad_field(self, block_layer):
        with pytest.raises(ValueError):
            Field(block_layer, 'not_a_field')

    def test_bad_expr(self, block_layer):
        with pytest.raises(ValueError):
            Field(block_layer, 'not_a_field + still_not', True)

    def test_getvalue_field(self, block_layer, field):
        f = next(block_layer.getFeatures())
        v = field.getValue(f)
        assert not field.hasError() and isinstance(v, str) and len(v) == 11

    def test_getvalue_expr(self, block_layer, expr):
        f = next(block_layer.getFeatures())
        v = expr.getValue(f)
        assert not expr.hasError()
        assert isinstance(v, str)
        assert len(v) == 11

    def test_makeqgsfield_field(self, field):
        qf = field.makeQgsField()
        assert qf.type() == QVariant.String

    def test_makeqgsfield_expr(self, expr):
        qf = expr.makeQgsField()
        assert qf.type() == QVariant.String

    def test_serialize(self, block_layer, field):
        data = field.serialize()
        assert data == {'layer': block_layer.id(),
                        'field': 'vtdid',
                        'expression': False,
                        'caption': 'vtdid'}

    def test_deserialize(self, block_layer):
        data = {'layer': block_layer.id(), 'field': 'vtdid', 'expression': False}
        field = Field.deserialize(data)
        assert field.field == 'vtdid'
        assert field.layer == block_layer
        assert not field.isExpression
        assert field.caption == 'vtdid'


class TestDataField:
    @pytest.fixture
    def data_field(self, block_layer) -> DataField:
        return DataField(block_layer, 'vap_ap_black', pctbase='vap_total')

    @pytest.fixture
    def data_field_expr(self, block_layer) -> DataField:
        return DataField(
            block_layer,
            'vap_nh_ap_black + vap_nh_asian + vap_nh_aiakn + vap_hispanic',
            caption='Dream Team',
            pctbase='vap_total'
        )

    def test_create(self, block_layer):
        field = DataField(block_layer, 'vap_ap_black', pctbase='vap_total')
        assert field.field == 'vap_ap_black' and field.sum and field.pctbase == 'vap_total'

    def test_create_expr(self, block_layer):
        field = DataField(block_layer, 'vap_nh_ap_black + vap_hispanic', True)
        assert field.field == 'vap_nh_ap_black + vap_hispanic' and field.sum and field.pctbase is None

    def test_serialize(self, block_layer, data_field):
        data = data_field.serialize()
        assert data == {
            'layer': block_layer.id(),
            'field': 'vap_ap_black',
            'expression': False,
            'caption': 'vap_ap_black',
            'sum': True,
            'pctbase': 'vap_total'
        }

    def test_deserialize(self, block_layer):
        data = {
            'layer': block_layer.id(),
            'field': 'vap_ap_black',
            'expression': False,
            'caption': 'APBVAP',
            'pctbase': 'vap_total'
        }
        field = DataField.deserialize(data)
        assert field.field == 'vap_ap_black'
        assert field.layer == block_layer
        assert not field.isExpression
        assert field.caption == 'APBVAP'
        assert field.sum  # pylint: disable=no-member
        assert field.pctbase == 'vap_total'  # pylint: disable=no-member

    def test_makeqgsfield_field(self, data_field):
        qf = data_field.makeQgsField()
        assert qf.type() == QVariant.LongLong

    def test_makeqgsfield_field_expr(self, data_field_expr):
        qf = data_field_expr.makeQgsField()
        assert qf.type() == QVariant.LongLong
