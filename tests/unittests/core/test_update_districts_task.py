"""QGIS Redistricting Plugin - unit tests for updating changes background task

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

import geopandas as gpd
import pytest
from pytest_mock import MockerFixture

import redistricting.services.updateservice  # noqa
from redistricting.models.plan import RdsPlan
from redistricting.services.district import DistrictUpdateParams, DistrictUpdater


class TestUpdateDistrictsTask:
    @pytest.fixture(scope="class", autouse=True)
    def patch_task(self, class_mocker: MockerFixture):
        class_mocker.patch("redistricting.services.updateservice.QgsApplication.taskManager")
        class_mocker.patch("redistricting.services.district.QgsTask.setDependentLayers")

    def test_create(self, plan: RdsPlan):
        updater = DistrictUpdater(plan)
        t = updater.update(plan, includeDemographics=True)
        assert t.task is not None

    def test_run(self, plan: RdsPlan):
        updater = DistrictUpdater(plan)
        params = DistrictUpdateParams(True, False)
        task, plan, params = updater._doUpdate(None, plan, params)
        assert isinstance(params, DistrictUpdateParams)
        assert params.totalPopulation == 227036
        assert params.populationData is not None
        assert list(params.populationData.columns) == [
            "district",
            "vtdid",
            "population",
            "vap_total",
            "vap_ap_black",
            "vap_nh_white",
            "vap_hispanic",
        ]
        assert params.districtData is not None
        assert not isinstance(params.districtData, gpd.GeoDataFrame)
        assert list(params.districtData.columns) == [
            "population",
            "vap_total",
            "vap_ap_black",
            "vap_nh_white",
            "vap_hispanic",
            "name",
            "members",
        ]
        assert params.geometry is None

        params = DistrictUpdateParams(False, True)
        task, plan, params = updater._doUpdate(None, plan, params)
        assert isinstance(params, DistrictUpdateParams)
        assert params.totalPopulation is None
        assert params.populationData is not None
        assert list(params.populationData.columns) == ["district", "vtdid", "geometry"]
        assert params.districtData is not None
        assert isinstance(params.districtData, gpd.GeoDataFrame)
        assert list(params.districtData.columns) == ["geometry", "name", "members"]
        assert params.geometry is not None
        assert len(params.geometry) == 5

        params = DistrictUpdateParams(True, True)
        task, plan, params = updater._doUpdate(None, plan, params)
        assert isinstance(params, DistrictUpdateParams)
        assert params.totalPopulation == 227036
        assert params.populationData is not None
        assert list(params.populationData.columns) == [
            "district",
            "vtdid",
            "population",
            "vap_total",
            "vap_ap_black",
            "vap_nh_white",
            "vap_hispanic",
            "geometry",
        ]
        assert params.districtData is not None
        assert isinstance(params.districtData, gpd.GeoDataFrame)
        assert list(params.districtData.columns) == [
            "population",
            "vap_total",
            "vap_ap_black",
            "vap_nh_white",
            "vap_hispanic",
            "geometry",
            "name",
            "members",
        ]
        assert params.geometry is not None
        assert len(params.geometry) == 5

    def test_run_subset(self, plan: RdsPlan):
        updater = DistrictUpdater(plan)
        params = DistrictUpdateParams(True, True, {2, 3})
        task, plan, params = updater._doUpdate(None, plan, params)
        assert isinstance(params, DistrictUpdateParams)
        assert params.totalPopulation == 227036
        assert params.populationData is not None
        assert list(params.populationData.columns) == [
            "district",
            "vtdid",
            "population",
            "vap_total",
            "vap_ap_black",
            "vap_nh_white",
            "vap_hispanic",
            "geometry",
        ]
        assert params.districtData is not None
        assert isinstance(params.districtData, gpd.GeoDataFrame)
        assert list(params.districtData.columns) == [
            "population",
            "vap_total",
            "vap_ap_black",
            "vap_nh_white",
            "vap_hispanic",
            "geometry",
            "name",
            "members",
        ]
        assert len(params.districtData) == 5
        assert len(params.districtData[params.districtData.geometry.notna()]) == 2
        assert params.geometry is not None
        assert len(params.geometry) == 2
