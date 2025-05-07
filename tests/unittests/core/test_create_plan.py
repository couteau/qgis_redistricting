"""QGIS Redistricting Plugin - unit tests for RdsPlan class

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

from redistricting.models.plan import RdsPlan
from redistricting.services import PlanBuilder
from redistricting.services.planbuilder import QgsApplication
from redistricting.services.tasks.createlayers import CreatePlanLayersTask

# pylint: disable=protected-access


class TestPlanCreator:
    @pytest.fixture
    def mock_geo_l(self, mocker: MockerFixture):
        return mocker.create_autospec(spec=QgsVectorLayer, instance=True)

    @pytest.fixture
    def creator(self, mock_geo_l):
        return (
            PlanBuilder()
            .setName("test")
            .setNumDistricts(5)
            .setGeoLayer(mock_geo_l)
            .setGeoIdField("geoid20")
            .setPopField("pop_total")
        )

    def test_createlayer_create(self, mocker: MockerFixture):
        layer = mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        creator = (
            PlanBuilder()
            .setName("test")
            .setNumDistricts(5)
            .setGeoLayer(layer)
            .setGeoIdField("geoid20")
            .setPopField("pop_total")
        )

        assert creator.validate()
        assert creator._numSeats == 5
        assert creator._geoLayer == layer
        assert creator._geoJoinField == "geoid20"
        assert creator._popJoinField == "geoid20"

    def test_createlayers_triggers_background_task_when_plan_is_valid(self, datadir, mocker: MockerFixture):
        mock = mocker.patch.object(QgsApplication.taskManager(), "addTask")
        mocker.patch("redistricting.services.planbuilder.RdsPlan", spec=RdsPlan)
        task_class = mocker.patch("redistricting.services.planbuilder.CreatePlanLayersTask", spec=CreatePlanLayersTask)
        task_class.return_value = mocker.create_autospec(spec=CreatePlanLayersTask, instance=True)
        task_class.return_value.taskCompleted = mocker.MagicMock()
        task_class.return_value.taskTerminated = mocker.MagicMock()
        task_class.return_value.progressChanged = mocker.MagicMock()

        c = (
            PlanBuilder()
            .setGeoPackagePath(str((datadir / "test_plan.gpkg").resolve()))
            .setName("test")
            .setNumDistricts(5)
            .setGeoLayer(mocker.create_autospec(spec=QgsVectorLayer, instance=True))
            .setGeoIdField("geoid20")
            .setPopField("pop_total")
        )
        c.createPlan()
        task = c._createLayersTask
        assert isinstance(task, CreatePlanLayersTask)
        assert not c.errors()
        mock.assert_called_once_with(task)

    def test_create_plan_create_layers_false(self, mocker: MockerFixture):
        layer = mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        layer.id.return_value = uuid4()
        layer.isValid.return_value = True
        plan_cls = mocker.patch("redistricting.services.planbuilder.RdsPlan", spec=RdsPlan)

        builder = (
            PlanBuilder()
            .setName("test")
            .setNumDistricts(5)
            .setGeoLayer(layer)
            .setGeoIdField("geoid20")
            .setPopField("pop_total")
        )

        builder.createPlan(createLayers=False)
        plan_cls.assert_called_once()
        assert builder._createLayersTask is None

    def test_create_plan_invalid_builder_no_plan(self, mocker: MockerFixture):
        layer = mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        layer.id.return_value = uuid4()
        layer.isValid.return_value = True
        plan_cls = mocker.patch("redistricting.services.planbuilder.RdsPlan", spec=RdsPlan)

        # no name
        builder = PlanBuilder().setNumDistricts(5).setGeoLayer(layer).setGeoIdField("geoid20").setPopField("pop_total")

        builder.createPlan(createLayers=False)
        plan_cls.assert_not_called()

        # no num districts
        builder = PlanBuilder().setName("test").setGeoLayer(layer).setGeoIdField("geoid20").setPopField("pop_total")

        builder.createPlan(createLayers=False)
        plan_cls.assert_not_called()

        # no geo layer
        builder = PlanBuilder().setName("test").setNumDistricts(5).setGeoIdField("geoid20").setPopField("pop_total")

        builder.createPlan(createLayers=False)
        plan_cls.assert_not_called()

        # no geo field
        builder = PlanBuilder().setName("test").setNumDistricts(5).setGeoLayer(layer).setPopField("pop_total")

        builder.createPlan(createLayers=False)
        plan_cls.assert_not_called()

        # no pop field
        builder = PlanBuilder().setName("test").setNumDistricts(5).setGeoLayer(layer).setGeoIdField("geoid20")

        builder.createPlan(createLayers=False)
        plan_cls.assert_not_called()

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
        assert ("Number of seats (30) must equal or exceed number of districts (45)", 2) in creator.errors()

    def test_set_num_districts(self, creator: PlanBuilder):
        with pytest.raises(ValueError, match="Invalid number of districts for plan"):
            creator.setNumDistricts(1)

        with pytest.raises(TypeError, match="Number of districts must be an integer"):
            creator.setNumDistricts("1")

    def test_validate_pop_layer_fields_not_found_no_validate(self, creator: PlanBuilder):
        assert creator._validatePopLayer()
        creator._popLayer.fields.return_value.lookupField.return_value = -1
        assert not creator._validatePopLayer()

    def test_create_attribute_indicies(self, creator: PlanBuilder):
        creator._geoLayer.storageType.return_value = "ESRI Shapefile"
        creator._geoLayer.fields.return_value.lookupField.return_value = 1
        creator.createAttributeIndices()
        assert creator._popLayer is creator._geoLayer
        creator._geoLayer.fields().lookupField.assert_called_once_with("geoid20")
        creator._geoLayer.dataProvider().createAttributeIndex.assert_called_once_with(1)

    def test_create_attribute_indicies_different_pop_layer(self, creator: PlanBuilder, mocker: MockerFixture):
        pop_layer: QgsVectorLayer = mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        pop_layer.storageType.return_value = "ESRI Shapefile"
        pop_layer.fields.return_value.lookupField.return_value = 2
        creator.setPopLayer(pop_layer)
        creator._geoLayer.storageType.return_value = "ESRI Shapefile"
        creator._geoLayer.fields.return_value.lookupField.return_value = 1
        creator.createAttributeIndices()
        creator._geoLayer.fields().lookupField.assert_called_once_with("geoid20")
        creator._geoLayer.dataProvider().createAttributeIndex.assert_called_once_with(1)
        creator._popLayer.fields().lookupField.assert_called_once_with("geoid20")
        creator._popLayer.dataProvider().createAttributeIndex.assert_called_once_with(2)

    def test_create_attribute_indicies_different_pop_join_field(self, creator: PlanBuilder, mocker: MockerFixture):
        pop_layer: QgsVectorLayer = mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        pop_layer.storageType.return_value = "ESRI Shapefile"
        pop_layer.fields.return_value.lookupField.return_value = 2
        creator.setPopLayer(pop_layer)
        creator.setPopJoinField("pop_join_field")
        creator._geoLayer.storageType.return_value = "ESRI Shapefile"
        creator._geoLayer.fields.return_value.lookupField.return_value = 1
        creator.createAttributeIndices()
        creator._geoLayer.fields().lookupField.assert_called_once_with("geoid20")
        creator._geoLayer.dataProvider().createAttributeIndex.assert_called_once_with(1)
        creator._popLayer.fields().lookupField.assert_called_once_with("pop_join_field")
        creator._popLayer.dataProvider().createAttributeIndex.assert_called_once_with(2)
