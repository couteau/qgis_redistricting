"""QGIS Redistricting Plugin - unit tests for Storage class"""
import pytest
from pytestqt.plugin import QtBot
from redistricting.core.Exception import RdsException
from redistricting.core.Plan import RedistrictingPlan

# pylint: disable=no-self-use


class TestPlan:
    def test_create(self, block_layer, gpkg_path):
        plan = RedistrictingPlan('test', 5)
        assert plan.name == 'test'
        assert plan.numDistricts == 5
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
        assert plan.cutEdges == 0
        assert len(plan.geoFields) == 0
        assert len(plan.dataFields) == 0
        assert len(plan.districts) == 1
        assert plan.districts[0].name == 'Unassigned'
        assert not plan.isValid()

        plan.popLayer = block_layer
        plan.popField = 'pop_total'
        plan.addLayersFromGeoPackage(gpkg_path)
        assert not plan.error()
        plan.geoIdField = 'geoid20'
        assert plan.isValid()

    def test_assign_props(self, block_layer, gpkg_path):
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

    def test_signals(self, qtbot: QtBot):
        plan = RedistrictingPlan('test', 45)
        with qtbot.waitSignal(plan.planChanged,
                              check_params_cb=lambda p, f, n, o:
                              p == plan and f == 'name' and n == 'new name' and o == 'test'
                              ):
            plan.name = 'new name'
        assert plan.name == 'new name'
