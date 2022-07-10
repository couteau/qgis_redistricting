"""QGIS Redistricting Plugin - unit tests for RedistrictingPlan class"""
import pathlib
import pytest

from qgis.core import QgsVectorLayer
from redistricting.core.Tasks.CreateLayersTask import CreatePlanLayersTask
from redistricting.core.Plan import RedistrictingPlan
from redistricting.core.Field import Field, DataField


class TestCreateLayersTask:
    @pytest.mark.parametrize(('datafields', 'geofields'), [
        ([], []),
        (['vap_apblack', 'vap_hispanic', 'vap_nh_white'], []),
        (['vap_apblack - vap_nh_black'], []),
        ([], ['countyid20', 'vtdid20']),
        ([], ['statefp20 || countyfp20']),
    ])
    def test_create_layers(self, block_layer, datadir: pathlib.Path, datafields, geofields):
        p = RedistrictingPlan('test_create_layers', 5)
        # pylint: disable=protected-access
        p._popLayer = block_layer
        p._geoIdField = 'geoid20'
        p._popField = 'pop_total'

        p._dataFields.extend([DataField(block_layer, f) for f in datafields])
        p._geoFields.extend([Field(block_layer, f) for f in geofields])
        gpkg = (datadir / 'test_create_layers.gpkg').resolve()
        task = CreatePlanLayersTask(p, str(gpkg), block_layer, 'geoid20')
        result = task.run()
        assert result
        assert gpkg.exists()

        a = QgsVectorLayer(f'{str(gpkg)}|layername=assignments')

        assert a.isValid()
        assert a.featureCount() == 6567
        for f in p.geoFields:
            assert a.fields().lookupField(f.fieldName) != -1

        d = QgsVectorLayer(f'{str(gpkg)}|layername=districts')

        assert d.isValid()
        assert d.featureCount() == 0
        for f in p.dataFields:
            assert d.fields().lookupField(f.fieldName) != -1

    def test_create_layers_cancel(self, block_layer, datadir: pathlib.Path):
        p = RedistrictingPlan('test_create_layers', 5)
        # pylint: disable=protected-access
        p._popLayer = block_layer
        p._geoIdField = 'geoid20'
        p._popField = 'pop_total'

        gpkg = (datadir / 'test_create_layers.gpkg').resolve()
        task = CreatePlanLayersTask(p, str(gpkg), block_layer, 'geoid20')
        task.cancel()
        result = task.run()
        assert not result
        assert task.isCanceled()
