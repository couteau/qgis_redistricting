"""QGIS Redistricting Plugin - integration tests

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

from redistricting.services import PlanBuilder

# pylint: disable=protected-access


class TestCreatePlan:
    @pytest.fixture
    def builder(self, block_layer):
        return PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setGeoLayer(block_layer) \
            .setGeoIdField('geoid') \
            .setPopField('pop_total')

    def test_set_nonexistent_fields_no_validate(self, builder: PlanBuilder):
        assert builder._validatePopLayer()
        builder.setPopJoinField('not_a_field')
        assert not builder._validatePopLayer()
        builder.setPopJoinField(None)

        assert builder._validatePopLayer()
        builder.setPopField('not_a_field')
        assert not builder._validatePopLayer()
        builder.setPopField('pop_total')

    def test_append_nonexistent_pop_field_no_validate(self, builder: PlanBuilder):
        assert builder._validatePopLayer()
        builder.appendPopField('not_a_field')
        assert not builder._validatePopLayer()

    def test_set_pop_field_updates_districts(self, builder: PlanBuilder):
        plan = builder.createPlan(createLayers=False)
        assert hasattr(plan.districts[0], 'population')

        builder.appendPopField('vap_total')
        plan = builder.createPlan(createLayers=False)
        assert plan is not None
        assert plan.popFields[0].field == 'vap_total'
        assert hasattr(plan.districts[0], 'vap_total')

    def test_append_nonexistent_data_field_no_validate(self, builder: PlanBuilder):
        assert builder._validatePopLayer()
        builder.appendDataField('not_a_field')
        assert not builder._validatePopLayer()

    def test_append_nonexistent_geo_field_no_validate(self, builder: PlanBuilder):
        assert builder._validateGeoLayer()
        builder.appendGeoField('not_a_field')
        assert not builder._validateGeoLayer()
