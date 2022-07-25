"""QGIS Redistricting Plugin - unit tests for RedistrictingPlan class"""
from uuid import UUID
import pytest
from pytest_mock.plugin import MockerFixture
from pytestqt.plugin import QtBot
from qgis.core import Qgis, QgsTask, QgsProject
from redistricting.core.Exception import RdsException
from redistricting.core import RedistrictingPlan, DataField, Field
import redistricting

# pylint: disable=too-many-public-methods


class TestPlan:
    @pytest.mark.parametrize('params',
                             [
                                 ['', 2],
                                 [None, 2],
                                 [True, 2],
                                 ['test', 1],
                                 ['test', 1.5],
                                 ['test', 2, False],
                                 ['test', 2, 'd2a95531-0de4-4556-bbe0-bb251d2f2026']
                             ])
    def test_create_plan_throws_valueerror_with_invalid_params(self, params):
        with pytest.raises(ValueError, match='Cannot create redistricting plan'):
            plan = RedistrictingPlan(*params)  # pylint: disable=unused-variable

    @pytest.mark.parametrize('params,expected',
                             [
                                 [['test'], ['test', 0, None]],
                                 [['test', 5],  ['test', 5, None]],
                                 [
                                     ['test', 2, UUID('d2a95531-0de4-4556-bbe0-bb251d2f2026')],
                                     ['test', 2, 'd2a95531-0de4-4556-bbe0-bb251d2f2026']
                                 ],
                             ])
    def test_create_plan_with_valid_params(self, params, expected):
        plan = RedistrictingPlan(*params)
        assert plan.name == expected[0]
        assert plan.numDistricts == expected[1]
        assert isinstance(plan.id, UUID)
        if expected[2]:
            assert str(plan.id) == expected[2]

    def test_create_plan_sets_expected_defaults(self):
        plan = RedistrictingPlan('test', 5)
        assert plan.name == 'test'
        assert plan.numSeats == 5
        assert plan.allocatedDistricts == 0
        assert plan.allocatedSeats == 0
        assert plan.assignLayer is None
        assert plan.distLayer is None
        assert plan.popLayer is None
        assert plan.joinField is None
        assert plan.sourceLayer is None
        assert plan.sourceIdField is None
        assert plan.distField == 'district'
        assert plan.geoIdField is None
        assert plan.popField is None
        assert plan.vapField is None
        assert plan.cvapField is None
        assert plan.geoDisplay is None
        assert plan.deviation == 0
        assert plan.totalPopulation == 0
        assert len(plan.geoFields) == 0
        assert len(plan.dataFields) == 0
        assert len(plan.districts) == 1
        assert plan.districts[0].name == 'Unassigned'

    def test_plan_is_not_valid(self):
        plan = RedistrictingPlan('test', 5)
        assert not plan.isValid()

    def test_plan_is_valid(self, block_layer, gpkg_path):
        plan = RedistrictingPlan('test', 5)
        plan.popLayer = block_layer
        plan.popField = 'pop_total'
        plan.addLayersFromGeoPackage(gpkg_path)
        assert not plan.error()
        assert plan.isValid()

    def test_assign_field_props(self, block_layer, gpkg_path):
        plan = RedistrictingPlan('test', 45)

        with pytest.raises(ValueError):
            plan.numSeats = 30
        assert plan.numSeats == 45
        plan.numSeats = 60
        assert plan.numSeats == 60
        plan.numDistricts = 75
        assert plan.numSeats == 75
        plan.numSeats = None
        assert plan.numSeats == 75
        with pytest.raises(ValueError):
            plan.numDistricts = 1

        plan.popLayer = block_layer
        assert plan.sourceLayer == block_layer

        with pytest.raises(RdsException):
            plan.joinField = 'not_a_field'

        with pytest.raises(RdsException):
            plan.popField = 'not_a_field'

        plan.popField = 'pop_total'
        assert plan.popField == 'pop_total'
        assert hasattr(plan.districts[0], 'pop_total')
        assert not plan.isValid()
        assert not plan.districts._needUpdate  # pylint: disable=protected-access

        with pytest.raises(RdsException):
            plan.vapField = 'not_a_field'

        plan.vapField = 'vap_total'
        assert plan.vapField == 'vap_total'
        assert hasattr(plan.districts[0], 'vap_total')

        with pytest.raises(RdsException):
            plan.cvapField = 'not_a_field'

        plan.cvapField = 'vap_hispanic'
        assert plan.cvapField == 'vap_hispanic'
        assert hasattr(plan.districts[0], 'vap_hispanic')

        plan.geoIdField = 'geoid20'
        assert plan.geoIdField == 'geoid20'
        assert plan.joinField == 'geoid20'
        assert plan.sourceIdField == 'geoid20'

        plan.addLayersFromGeoPackage(gpkg_path)
        with pytest.raises(RdsException):
            plan.geoIdField = 'not_a_field'

    def test_assign_name_updates_layer_names(self, block_layer, gpkg_path):
        plan = RedistrictingPlan('oldname', 45)
        plan.popLayer = block_layer
        plan.addLayersFromGeoPackage(gpkg_path)
        assert plan.distLayer.name() == 'oldname_districts'
        assert plan.assignLayer.name() == 'oldname_assignments'
        plan.name = 'newname'
        assert plan.distLayer.name() == 'newname_districts'
        assert plan.assignLayer.name() == 'newname_assignments'

    def test_signals(self, block_layer, qtbot: QtBot):
        plan = RedistrictingPlan('test', 45)
        with qtbot.waitSignal(plan.planChanged,
                              check_params_cb=lambda p, f, n, o:
                              p == plan and f == 'name' and n == 'new name' and o == 'test'
                              ):
            plan.name = 'new name'
        assert plan.name == 'new name'

        plan.popLayer = block_layer
        with qtbot.waitSignals([plan.dataFieldAdded, plan.planChanged]):
            plan.appendDataField('vap_nh_black')
        assert len(plan.dataFields) == 1

        with qtbot.waitSignals([plan.dataFieldRemoved, plan.planChanged]):
            plan.removeDataField('vap_nh_black')
        assert len(plan.dataFields) == 0

        with qtbot.waitSignals([plan.geoFieldAdded, plan.planChanged]):
            plan.appendGeoField('vtdid20')
        assert len(plan.geoFields) == 1

        with qtbot.waitSignals([plan.geoFieldRemoved, plan.planChanged]):
            plan.removeGeoField(0)
        assert len(plan.geoFields) == 0

    @pytest.fixture
    def bvap_field_fld(self, block_layer):
        return DataField(block_layer, 'vap_nh_black', False)

    @pytest.fixture
    def bvap_field_str(self):
        return'vap_nh_black'

    def test_datafields_append_sets_parent(self, plan_with_pop_layer: RedistrictingPlan):
        plan_with_pop_layer.appendDataField('vap_apblack', False, 'APBVAP')
        assert plan_with_pop_layer.dataFields[0].parent() == plan_with_pop_layer.dataFields

    def test_datafields_append_adds_field(self, plan_with_pop_layer: RedistrictingPlan, block_layer, qtbot: QtBot):
        with qtbot.waitSignal(plan_with_pop_layer.dataFields.fieldAdded):
            plan_with_pop_layer.appendDataField('vap_apblack', False, 'APBVAP')
        assert len(plan_with_pop_layer.dataFields) == 1
        assert isinstance(plan_with_pop_layer.dataFields[0], DataField)
        assert plan_with_pop_layer.dataFields[0].parent() == plan_with_pop_layer.dataFields
        assert plan_with_pop_layer.dataFields[0].layer == block_layer
        assert plan_with_pop_layer.dataFields[0].field == 'vap_apblack'
        assert not plan_with_pop_layer.dataFields[0].isExpression
        assert plan_with_pop_layer.dataFields[0].caption == 'APBVAP'
        f1 = DataField(block_layer, 'pop_apblack', False, caption='APBPOP')
        with qtbot.waitSignal(plan_with_pop_layer.dataFields.fieldAdded):
            plan_with_pop_layer.appendDataField(f1)
        assert len(plan_with_pop_layer.dataFields) == 2
        assert isinstance(plan_with_pop_layer.dataFields[1], DataField)
        assert plan_with_pop_layer.dataFields[1].parent() == plan_with_pop_layer.dataFields
        assert plan_with_pop_layer.dataFields[1].field == 'pop_apblack'

        plan_with_pop_layer.appendDataField('vap_nh_white')
        assert len(plan_with_pop_layer.dataFields) == 3

    @pytest.mark.parametrize('field', ['bvap_field_str', 'bvap_field_fld'])
    def test_datafields_set_error_when_duplicate_field_added(
        self,
        plan_with_pop_layer: RedistrictingPlan,
        field,
        request
    ):
        plan_with_pop_layer.appendDataField('vap_nh_black', False, 'BVAP')
        plan_with_pop_layer.appendDataField(request.getfixturevalue(field))
        assert len(plan_with_pop_layer.dataFields) == 1
        assert plan_with_pop_layer.error() == \
            ('Attempt to add duplicate field vap_nh_black to plan minimal', Qgis.Warning)

    def test_datafields_throw_exception_when_invalid_field_added(self, plan_with_pop_layer: RedistrictingPlan):
        with pytest.raises(ValueError):
            plan_with_pop_layer.appendDataField(1)

    def test_datafields_throw_exception_when_bad_field_added(self, plan_with_pop_layer: RedistrictingPlan):
        with pytest.raises(RdsException):
            plan_with_pop_layer.appendDataField('not_a_field')

    def test_datafields_throw_exception_when_non_existent_field_removed(
        self,
        plan_with_pop_layer: RedistrictingPlan,
        bvap_field_fld
    ):
        with pytest.raises(ValueError):
            plan_with_pop_layer.removeDataField('vap_hispanic')

        with pytest.raises(ValueError):
            plan_with_pop_layer.removeDataField(bvap_field_fld)

        with pytest.raises(ValueError):
            plan_with_pop_layer.removeDataField(3)

    def test_datafields_remove_field(self, plan_with_pop_layer: RedistrictingPlan, qtbot: QtBot):
        plan_with_pop_layer.appendDataField('pop_apblack')
        plan_with_pop_layer.appendDataField('vap_apblack')
        plan_with_pop_layer.appendDataField('vap_nh_white')
        f1 = plan_with_pop_layer.dataFields[0]

        with qtbot.waitSignal(plan_with_pop_layer.dataFields.fieldRemoved):
            plan_with_pop_layer.removeDataField('vap_apblack')
        assert len(plan_with_pop_layer.dataFields) == 2
        assert plan_with_pop_layer.dataFields[0].field == 'pop_apblack'
        assert plan_with_pop_layer.dataFields[1].field == 'vap_nh_white'

        with qtbot.waitSignal(plan_with_pop_layer.dataFields.fieldRemoved):
            plan_with_pop_layer.removeDataField(f1)
        assert len(plan_with_pop_layer.dataFields) == 1
        assert plan_with_pop_layer.dataFields[0].field == 'vap_nh_white'

        with qtbot.waitSignal(plan_with_pop_layer.dataFields.fieldRemoved):
            plan_with_pop_layer.removeDataField(0)
        assert len(plan_with_pop_layer.dataFields) == 0

    @pytest.fixture
    def vtd_field_fld(self, block_layer):
        return Field(block_layer, 'vtdid20', False)

    @pytest.fixture
    def vtd_field_str(self):
        return'vtdid20'

    def test_geofields_append_sets_parent(self, plan_with_pop_layer: RedistrictingPlan):
        plan_with_pop_layer.appendGeoField('vtdid20')
        assert plan_with_pop_layer.geoFields[0].parent() == plan_with_pop_layer.geoFields

    def test_geofields_assign(self, plan_with_pop_layer, vtd_field_fld, qtbot: QtBot):
        with qtbot.waitSignal(plan_with_pop_layer.planChanged):
            plan_with_pop_layer.geoFields = [vtd_field_fld]
        assert len(plan_with_pop_layer.geoFields) == 1
        assert len(plan_with_pop_layer.stats.splits) == 1

    def test_geofields_append_adds_field(self, plan_with_pop_layer: RedistrictingPlan, block_layer, qtbot: QtBot):
        with qtbot.waitSignal(plan_with_pop_layer.geoFields.fieldAdded):
            plan_with_pop_layer.appendGeoField('vtdid20', False, 'VTD')
        assert len(plan_with_pop_layer.geoFields) == 1
        assert isinstance(plan_with_pop_layer.geoFields[0], Field)
        assert plan_with_pop_layer.geoFields[0].parent() == plan_with_pop_layer.geoFields
        assert plan_with_pop_layer.geoFields[0].layer == block_layer
        assert plan_with_pop_layer.geoFields[0].field == 'vtdid20'
        assert not plan_with_pop_layer.geoFields[0].isExpression
        assert plan_with_pop_layer.geoFields[0].caption == 'VTD'

        f1 = Field(block_layer, 'statefp20 || countyfp20 || vtd', True, caption='VTD')
        with qtbot.waitSignal(plan_with_pop_layer.geoFields.fieldAdded):
            plan_with_pop_layer.appendGeoField(f1)
        assert len(plan_with_pop_layer.geoFields) == 2
        assert plan_with_pop_layer.geoFields[1].parent() == plan_with_pop_layer.geoFields
        assert plan_with_pop_layer.geoFields[1].field == 'statefp20 || countyfp20 || vtd'
        assert plan_with_pop_layer.geoFields[1].isExpression

        plan_with_pop_layer.appendGeoField('countyid20')
        assert len(plan_with_pop_layer.geoFields) == 3

    @pytest.mark.parametrize('field', ['vtd_field_str', 'vtd_field_fld'])
    def test_geofields_set_error_when_duplicate_field_added(
        self,
        plan_with_pop_layer: RedistrictingPlan,
        field,
        request
    ):
        plan_with_pop_layer.appendGeoField('vtdid20', False, 'VTD')
        plan_with_pop_layer.appendGeoField(request.getfixturevalue(field))
        assert len(plan_with_pop_layer.geoFields) == 1
        assert plan_with_pop_layer.error() == ('Attempt to add duplicate field vtdid20 to plan minimal', Qgis.Warning)

    def test_geofields_throw_exception_when_invalid_field_added(
        self,
        plan_with_pop_layer: RedistrictingPlan
    ):
        with pytest.raises(ValueError):
            plan_with_pop_layer.appendGeoField(1)

    def test_geofields_throw_exception_when_bad_field_added(self, plan_with_pop_layer: RedistrictingPlan):
        with pytest.raises(RdsException):
            plan_with_pop_layer.appendGeoField('not_a_field')

    def test_geofields_throw_exception_when_nonexistent_field_removed(
        self,
        plan_with_pop_layer: RedistrictingPlan,
        vtd_field_fld
    ):
        with pytest.raises(ValueError):
            plan_with_pop_layer.removeGeoField('blockid20')

        with pytest.raises(ValueError):
            plan_with_pop_layer.removeGeoField(vtd_field_fld)

        with pytest.raises(ValueError):
            plan_with_pop_layer.removeGeoField(3)

    def test_geofields_remove_field(
        self,
        plan_with_pop_layer: RedistrictingPlan,
        vtd_field_fld,
        qtbot: QtBot
    ):
        plan_with_pop_layer.appendGeoField(vtd_field_fld)
        plan_with_pop_layer.appendGeoField('statefp20 || countyfp20 || vtd', True)
        plan_with_pop_layer.appendGeoField('countyid20')
        f1 = plan_with_pop_layer.geoFields[1]

        with qtbot.waitSignals((plan_with_pop_layer.geoFields.fieldRemoved, plan_with_pop_layer.geoFieldRemoved, plan_with_pop_layer.planChanged)):
            plan_with_pop_layer.removeGeoField('vtdid20')
        assert len(plan_with_pop_layer.geoFields) == 2
        assert plan_with_pop_layer.geoFields[0].field == 'statefp20 || countyfp20 || vtd'
        assert plan_with_pop_layer.geoFields[1].field == 'countyid20'

        with qtbot.waitSignal(plan_with_pop_layer.geoFields.fieldRemoved):
            plan_with_pop_layer.removeGeoField(f1)
        assert len(plan_with_pop_layer.geoFields) == 1
        assert plan_with_pop_layer.geoFields[0].field == 'countyid20'

        with qtbot.waitSignal(plan_with_pop_layer.geoFields.fieldRemoved):
            plan_with_pop_layer.removeGeoField(0)
        assert len(plan_with_pop_layer.geoFields) == 0

    def test_addgeopackage_sets_error_package_doesnt_exist(self, datadir):
        plan = RedistrictingPlan('test', 5)
        gpkg = datadir / 'dummy.gpkg'
        plan.addLayersFromGeoPackage(gpkg)
        assert plan.error() is not None

    def test_addgeopackage_adds_layers_to_project_and_group_when_valid_gpkg(self, datadir):
        plan = RedistrictingPlan('test', 5)
        gpkg = datadir / 'tuscaloosa_plan.gpkg'
        plan.addLayersFromGeoPackage(gpkg)
        assert plan.error() is None
        assert plan.assignLayer.name() == 'test_assignments'
        assert plan.distLayer.name() == 'test_districts'
        assert QgsProject.instance().mapLayersByName('test_assignments')
        assert QgsProject.instance().mapLayersByName('test_districts')
        assert plan.geoIdField == 'geoid20'
        assert plan._group._group.findLayer(plan.assignLayer.id())  # pylint: disable=protected-access
        assert plan._group._group.findLayer(plan.distLayer.id())  # pylint: disable=protected-access

    def test_createlayers_set_error_when_plan_is_invalid(self, datadir):
        plan = RedistrictingPlan('test', 5)
        assert plan.createLayers(datadir / 'test_plan.gpkg') is None
        assert plan.error() == ('Plan name, source layer, geography id field, and population field must be set '
                                'before creating redistricting plan layers', Qgis.Critical)

    def test_createlayers_triggers_background_task_when_plan_is_valid(
        self,
        datadir,
        block_layer,
        mocker: MockerFixture
    ):
        plan = RedistrictingPlan('test', 5)
        gpkg = (datadir / 'tuscaloosa_plan.gpkg').resolve()
        plan.addLayersFromGeoPackage(gpkg)

        mock = mocker.patch.object(redistricting.core.Plan.QgsApplication.taskManager(), 'addTask')
        plan.popLayer = block_layer
        plan.geoIdField = 'geoid20'
        plan.popField = 'pop_total'
        task = plan.createLayers(datadir / 'test_plan.gpkg')
        assert isinstance(task, QgsTask)
        assert plan.error() is None
        mock.assert_called_once_with(task)
