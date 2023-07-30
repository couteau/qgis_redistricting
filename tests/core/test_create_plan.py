"""QGIS Redistricting Plugin - unit tests for RedistrictingPlan class

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
from pytest_mock.plugin import MockerFixture
from qgis.core import QgsTask

from redistricting.core import PlanBuilder
from redistricting.core.PlanBuilder import QgsApplication

# pylint: disable=protected-access


class TestPlanCreator:

    @pytest.fixture
    def creator(self, block_layer):
        return PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setPopLayer(block_layer) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total')

    def test_createlayer_create(self, block_layer):
        creator = PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setPopLayer(block_layer) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total')

        assert creator.validate()
        assert creator._numSeats == 5
        assert creator._geoLayer == block_layer
        assert creator._sourceIdField == 'geoid20'
        assert creator._popJoinField == 'geoid20'

    def test_createlayers_triggers_background_task_when_plan_is_valid(
        self,
        datadir,
        block_layer,
        mocker: MockerFixture
    ):
        mock = mocker.patch.object(QgsApplication.taskManager(), 'addTask')

        c = PlanBuilder() \
            .setGeoPackagePath(str((datadir / 'test_plan.gpkg').resolve())) \
            .setName('test') \
            .setNumDistricts(5) \
            .setPopLayer(block_layer) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total')
        c.createPlan()
        task = c._createLayersTask
        assert isinstance(task, QgsTask)
        assert not c.errors()
        mock.assert_called_once_with(task)

    def test_plan_is_valid(self, block_layer, gpkg_path):
        plan = PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setPopLayer(block_layer) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total') \
            .createPlan(createLayers=False)
        plan.addLayersFromGeoPackage(gpkg_path)
        assert plan.isValid()

    def test_set_num_seats(self, creator: PlanBuilder):
        creator.setNumDistricts(45)
        assert creator._numSeats == 45

        creator.setNumSeats(60)
        assert creator._numSeats == 60

        creator.setNumDistricts(75)
        assert creator._numSeats == 75

        creator.setNumDistricts(45)
        assert creator._numSeats == 45

        creator.setNumSeats(30)
        assert not creator.validate()
        assert \
            ('Number of seats (30) must equal or exceed number of districts (45)', 2) \
            in creator.errors()

    def test_set_num_districts(self, creator: PlanBuilder):
        with pytest.raises(ValueError):
            creator.setNumDistricts(1)

        with pytest.raises(ValueError):
            creator.setNumDistricts('1')

    def test_set_nonexistent_fields_no_validate(self, creator: PlanBuilder):
        assert creator._validatePopLayer()
        creator.setJoinField('not_a_field')
        assert not creator._validatePopLayer()
        creator.setJoinField(None)

        assert creator._validatePopLayer()
        creator.setPopField('not_a_field')
        assert not creator._validatePopLayer()
        creator.setPopField('pop_total')

        assert creator._validatePopLayer()
        creator.setVAPField('not_a_field')
        assert not creator._validatePopLayer()
        creator.setVAPField(None)

        assert creator._validatePopLayer()
        creator.setCVAPField('not_a_field')
        assert not creator._validatePopLayer()
        creator.setCVAPField(None)

    def test_set_pop_field_updates_districts(self, creator: PlanBuilder):
        plan = creator.createPlan(createLayers=False)
        assert hasattr(plan.districts[0], 'pop_total')
        assert not plan.districts._needUpdate

        creator.setVAPField('vap_total')
        plan = creator.createPlan(createLayers=False)
        assert plan.vapField == 'vap_total'
        assert hasattr(plan.districts[0], 'vap_total')

        creator.setCVAPField('vap_hispanic')
        plan = creator.createPlan(createLayers=False)
        assert plan.cvapField == 'vap_hispanic'
        assert hasattr(plan.districts[0], 'vap_hispanic')
