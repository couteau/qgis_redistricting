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
from uuid import uuid4

import pytest
from pytest_mock.plugin import MockerFixture
from qgis.core import QgsVectorLayer

from redistricting.models.Plan import RedistrictingPlan
from redistricting.services import PlanBuilder
from redistricting.services.PlanBuilder import QgsApplication
from redistricting.services.Tasks import CreatePlanLayersTask

# pylint: disable=protected-access


class TestPlanCreator:
    @pytest.fixture
    def mock_geo_l(self, mocker: MockerFixture):
        return mocker.create_autospec(spec=QgsVectorLayer, instance=True)

    @pytest.fixture
    def creator(self, mock_geo_l):
        return PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setGeoLayer(mock_geo_l) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total')

    def test_createlayer_create(self, mocker: MockerFixture):
        layer = mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        creator = PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setGeoLayer(layer) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total')

        assert creator.validate()
        assert creator._numSeats == 5
        assert creator._geoLayer == layer
        assert creator._geoJoinField == 'geoid20'
        assert creator._popJoinField == 'geoid20'

    def test_createlayers_triggers_background_task_when_plan_is_valid(
        self,
        datadir,
        mocker: MockerFixture
    ):
        mock = mocker.patch.object(QgsApplication.taskManager(), 'addTask')
        plan_class = mocker.patch('redistricting.services.PlanBuilder.RedistrictingPlan', spec=RedistrictingPlan)
        plan_class.deserialize.return_value = mocker.create_autospec(spec=RedistrictingPlan, instance=True)
        task_class = mocker.patch('redistricting.services.PlanBuilder.CreatePlanLayersTask', spec=CreatePlanLayersTask)
        task_class.return_value = mocker.create_autospec(spec=CreatePlanLayersTask, instance=True)
        task_class.return_value.taskCompleted = mocker.MagicMock()
        task_class.return_value.taskTerminated = mocker.MagicMock()
        task_class.return_value.progressChanged = mocker.MagicMock()

        c = PlanBuilder() \
            .setGeoPackagePath(str((datadir / 'test_plan.gpkg').resolve())) \
            .setName('test') \
            .setNumDistricts(5) \
            .setGeoLayer(mocker.create_autospec(spec=QgsVectorLayer, instance=True)) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total')
        c.createPlan()
        task = c._createLayersTask
        assert isinstance(task, CreatePlanLayersTask)
        assert not c.errors()
        mock.assert_called_once_with(task)

    def test_create_plan_create_layers_false(self, mocker: MockerFixture):
        layer = mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        layer.id.return_value = uuid4()
        layer.isValid.return_value = True
        plan_class = mocker.patch('redistricting.services.PlanBuilder.RedistrictingPlan', spec=RedistrictingPlan)
        plan_class.deserialize.return_value = mocker.create_autospec(spec=RedistrictingPlan, instance=True)

        builder = PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setGeoLayer(layer) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total')

        builder.createPlan(createLayers=False)
        plan_class.deserialize.assert_called_once()
        json = plan_class.deserialize.call_args[0][0]
        assert {'name': 'test', 'description': '', 'deviation': 0.0, 'num-districts': 5,
                'geo-layer': layer.id(), 'geo-id-field': 'geoid20', 'pop-field': 'pop_total',
                'geo-fields': [], 'data-fields': [], 'pop-fields': []}.items() <= json.items()
        assert builder._createLayersTask is None

    def test_create_plan_invalid_builder_no_plan(self, mocker: MockerFixture):
        layer = mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        layer.id.return_value = uuid4()
        layer.isValid.return_value = True
        plan_class = mocker.patch('redistricting.services.PlanBuilder.RedistrictingPlan', spec=RedistrictingPlan)
        plan_class.deserialize.return_value = mocker.create_autospec(spec=RedistrictingPlan, instance=True)

        # no name
        builder = PlanBuilder() \
            .setNumDistricts(5) \
            .setGeoLayer(layer) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total')

        builder.createPlan(createLayers=False)
        plan_class.deserialize.assert_not_called()

        # no num districts
        builder = PlanBuilder() \
            .setName('test') \
            .setGeoLayer(layer) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total')

        builder.createPlan(createLayers=False)
        plan_class.deserialize.assert_not_called()

        # no geo layer
        builder = PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setGeoIdField('geoid20') \
            .setPopField('pop_total')

        builder.createPlan(createLayers=False)
        plan_class.deserialize.assert_not_called()

        # no geo field
        builder = PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setGeoLayer(layer) \
            .setPopField('pop_total')

        builder.createPlan(createLayers=False)
        plan_class.deserialize.assert_not_called()

        # no pop field
        builder = PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setGeoLayer(layer) \
            .setGeoIdField('geoid20')

        builder.createPlan(createLayers=False)
        plan_class.deserialize.assert_not_called()

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

    def test_validate_pop_layer_fields_not_found_no_validate(self, creator: PlanBuilder):
        assert creator._validatePopLayer()
        creator._popLayer.fields.return_value.lookupField.return_value = -1
        assert not creator._validatePopLayer()

    def test_append_nonexistent_field_raises_error(self, creator: PlanBuilder, mock_geo_l: QgsVectorLayer):
        assert creator._validatePopLayer()
        mock_geo_l.fields.return_value.lookupField.return_value = -1
        with pytest.raises(ValueError):
            creator.appendPopField('not_a_field')
