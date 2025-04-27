"""QGIS Redistricting Plugin - unit tests for the create district layers
    background task

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
import pathlib

import pytest
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsVectorLayer
)

from redistricting.models import (
    RdsDataField,
    RdsField,
    RdsPlan
)
from redistricting.services.tasks.createlayers import CreatePlanLayersTask

# pylint: disable=protected-access


class TestCreateLayersTask:
    @pytest.mark.parametrize(('sourcefile', 'pop_field', 'geoid_field'), [
        ('tuscaloosa_blocks.gpkg|layername=plans', 'pop_total', 'geoid20'),
        ('tuscaloosa_pl2020_b.shp', 'P0010001', 'GEOID20'),
        ('tuscaloosa_pl2020_b.geojson', 'P0010001', 'GEOID20')
    ])
    def test_create_layers_formats(self, datadir: pathlib.Path, sourcefile, pop_field, geoid_field):
        path = datadir / sourcefile
        layer = QgsVectorLayer(str(path), 'blocks', 'ogr')
        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4269"), False)
        QgsProject.instance().addMapLayer(layer, False)

        p = RdsPlan('test_create_layers', 5)
        p._geoIdField = geoid_field
        p._popLayer = layer
        p._popJoinField = geoid_field
        p._popField = pop_field
        p._geoLayer = layer
        p._geoJoinField = geoid_field
        gpkg = (datadir / 'test_create_layers.gpkg').resolve()
        task = CreatePlanLayersTask(p, str(gpkg), layer, geoid_field)
        result = task.run()
        assert task.exception is None
        assert result
        assert gpkg.exists()

    @pytest.mark.parametrize(('datafields', 'geofields'), [
        ([], []),
        (['vap_ap_black', 'vap_hispanic', 'vap_nh_white'], []),
        (['vap_ap_black - vap_nh_black'], []),
        (['vap_ap_black', 'vap_ap_black - vap_nh_black', 'vap_hispanic', 'vap_nh_white'], []),
        (['vap_ap_black - vap_nh_black', 'vap_ap_black', 'vap_hispanic', 'vap_nh_white'], []),
        ([], ['countyid', 'vtdid']),
        ([], ['statefp || countyfp']),
    ])
    def test_create_layers_with_fields(self, block_layer, datadir: pathlib.Path, datafields, geofields):
        p = RdsPlan('test_create_layers', 5)
        p._popLayer = block_layer
        p._geoIdField = 'geoid'
        p._popField = 'pop_total'

        p.dataFields.extend([RdsDataField(block_layer, f) for f in datafields])
        p.geoFields.extend([RdsField(block_layer, f) for f in geofields])
        gpkg = (datadir / 'test_create_layers.gpkg').resolve()
        task = CreatePlanLayersTask(p, str(gpkg), block_layer, 'geoid')
        result = task.run()
        assert task.exception is None
        assert result
        assert task.totalPopulation == 227036
        assert gpkg.exists()
        try:
            a = QgsVectorLayer(f'{str(gpkg)}|layername=assignments')

            assert a.isValid()
            assert a.featureCount() == 6567
            for f in p.geoFields:
                assert a.fields().lookupField(f.fieldName) != -1
            del a

            d = QgsVectorLayer(f'{str(gpkg)}|layername=districts')
            try:
                assert d.isValid()
                assert d.featureCount() == 1
                for f in p.dataFields:  # pylint: disable=not-an-iterable
                    assert d.fields().lookupField(f.fieldName) != -1
            finally:
                del d
        finally:
            p._setAssignLayer(None)
            p._setDistLayer(None)

    def test_create_layers_cancel(self, block_layer, datadir: pathlib.Path):
        p = RdsPlan('test_create_layers', 5)
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
