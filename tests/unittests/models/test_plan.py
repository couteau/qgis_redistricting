"""QGIS Redistricting Plugin - unit tests for RdsPlan class

Copyright (C) 2025, Stuart C. Naifeh

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

from uuid import UUID

import pytest
from pytestqt.plugin import QtBot

# pylint: disable-next=unused-import
from redistricting.models import (
    DeviationType,
    FieldCategory,
    RdsDataField,
    RdsDistrict,
    RdsField,
    RdsPlan,
    metrics,  # noqa: F401
)
from redistricting.models.serialization import deserialize, serialize

# pylint: disable=too-many-public-methods,protected-access


class TestPlan:
    @pytest.mark.parametrize(
        "params",
        [
            {"name": "test"},
            {"name": None, "numDistricts": 2},
            {"name": True, "numDistricts": 2},
            {"name": "test", "numDistricts": 2.5},
            {"name": "test", "numDistricts": 2, "id": False},
            {"name": "test", "numDistricts": 2, "id": "d2a95531-0de4-4556-bbe0-bb251d2f2026"},
        ],
    )
    def test_create_plan_throws_typeerror_with_wrong_type_params(self, params):
        with pytest.raises(TypeError):
            plan = RdsPlan(**params)  # noqa: F841 # pylint: disable=unused-variable

    @pytest.mark.parametrize(
        ("params", "message"),
        [
            ({"name": "", "numDistricts": 2}, "Value must not be empty"),
            ({"name": "test", "numDistricts": 1}, "Value must be between"),
            ({"name": "test", "numDistricts": 2001}, "Value must be between"),
        ],
    )
    def test_create_plan_throws_valueerror_with_invalid_params(self, params, message):
        with pytest.raises(ValueError, match=message):
            plan = RdsPlan(**params)  # noqa: F841 # pylint: disable=unused-variable

    def test_set_invalid_numdistricts_raises_value_error(self):
        p = RdsPlan("test", 5)
        with pytest.raises(ValueError, match="Value must be between"):
            p.numDistricts = 1

    @pytest.mark.parametrize(
        ("params", "expected"),
        [
            ({"name": "test", "numDistricts": 5}, ["test", 5, None]),
            (
                {"name": "test", "numDistricts": 2, "id": UUID("d2a95531-0de4-4556-bbe0-bb251d2f2026")},
                ["test", 2, "d2a95531-0de4-4556-bbe0-bb251d2f2026"],
            ),
        ],
    )
    def test_create_plan_with_valid_params(self, params, expected):
        plan = RdsPlan(**params)
        assert plan.name == expected[0]
        assert plan.numDistricts == expected[1]
        assert isinstance(plan.id, UUID)
        if expected[2]:
            assert str(plan.id) == expected[2]

    def test_repr(self, plan):
        s = repr(plan)
        assert s

    def test_create_plan_sets_expected_defaults(self):
        plan = RdsPlan("test", 5)
        assert plan.name == "test"
        assert plan.numSeats == 5
        assert plan.assignLayer is None
        assert plan.distLayer is None
        assert plan.popLayer is None
        assert plan.popJoinField is None
        assert plan.geoLayer is None
        assert plan.geoJoinField is None
        assert plan.distField == "district"
        assert plan.geoIdField is None
        assert plan.popField is None
        assert len(plan.popFields) == 0
        assert plan.geoIdCaption is None
        assert plan.deviation == 0
        assert plan.totalPopulation == 0
        assert len(plan.geoFields) == 0
        assert len(plan.dataFields) == 0
        assert len(plan.districts) == 1
        assert plan.districts[0].name == "Unassigned"

    def test_new_plan_is_not_valid(self):
        plan = RdsPlan("test", 5)
        assert not plan.isValid()

    def test_assign_name_updates_layer_names(self, plan_gpkg_path, qtbot: QtBot):
        plan = RdsPlan("oldname", 45)
        plan.addLayersFromGeoPackage(plan_gpkg_path)
        try:
            assert plan.distLayer.name() == "oldname_districts"
            assert plan.assignLayer.name() == "oldname_assignments"
            with qtbot.wait_signal(plan.nameChanged):
                plan.name = "newname"
            assert plan.distLayer.name() == "newname_districts"
            assert plan.assignLayer.name() == "newname_assignments"
        finally:
            plan._setAssignLayer(None)
            plan._setDistLayer(None)

    def test_datafields_assign(self, valid_plan: RdsPlan, block_layer, qtbot: QtBot):
        with qtbot.waitSignal(valid_plan.dataFieldsChanged):
            valid_plan.dataFields = [RdsDataField(block_layer, "vap_nh_black")]

        assert len(valid_plan.dataFields) == 1

    # pylint: disable-next=unused-argument
    def test_geofields_assign(self, valid_plan: RdsPlan, block_layer, mock_taskmanager, qtbot: QtBot):
        with qtbot.waitSignal(valid_plan.geoFieldsChanged):
            valid_plan.geoFields = {"vtdid20": RdsField(block_layer, "vtdid20")}
        assert len(valid_plan.geoFields) == 1

    def test_addgeopackage_sets_error_package_doesnt_exist(self, datadir):
        plan = RdsPlan("test", 5)
        gpkg = datadir / "dummy.gpkg"
        with pytest.raises(ValueError, match=f"File {gpkg} does not exist"):
            plan.addLayersFromGeoPackage(gpkg)

    def test_addgeopackage_adds_layers_to_project_when_valid_gpkg(self, datadir):
        plan = RdsPlan("test", 5)
        gpkg = datadir / "tuscaloosa_plan.gpkg"
        plan.addLayersFromGeoPackage(gpkg)
        assert plan.assignLayer.name() == "test_assignments"
        assert plan.distLayer.name() == "test_districts"
        assert plan.geoIdField == "geoid"
        plan._setAssignLayer(None)
        plan._setDistLayer(None)

    def test_serialize(self, plan: RdsPlan, block_layer, assign_layer, dist_layer):
        data = serialize(plan)
        assert data == {
            "id": str(plan.id),
            "name": "test",
            "description": "",
            "num-districts": 5,
            "num-seats": 5,
            "deviation": 0.025,
            "deviation-type": DeviationType.OverUnder,
            "geo-layer": block_layer.id(),
            "geo-join-field": "geoid",
            "pop-layer": block_layer.id(),
            "pop-join-field": "geoid",
            "pop-field": "pop_total",
            "pop-fields": {
                "vap_total": {
                    "layer": block_layer.id(),
                    "field": "vap_total",
                    "caption": "VAP",
                    "category": FieldCategory.Population,
                }
            },
            "assign-layer": assign_layer.id(),
            "geo-id-field": "geoid",
            "geo-id-caption": "geoid",
            "dist-layer": dist_layer.id(),
            "dist-field": "district",
            "data-fields": {
                "vap_ap_black": {
                    "layer": block_layer.id(),
                    "field": "vap_ap_black",
                    "caption": "APBVAP",
                    "category": FieldCategory.Demographic,
                    "sum-field": True,
                    "pct-base": "vap_total",
                },
                "vap_nh_white": {
                    "layer": block_layer.id(),
                    "field": "vap_nh_white",
                    "caption": "WVAP",
                    "category": FieldCategory.Demographic,
                    "sum-field": True,
                    "pct-base": "vap_total",
                },
                "vap_hispanic": {
                    "layer": block_layer.id(),
                    "field": "vap_hispanic",
                    "caption": "HVAP",
                    "category": FieldCategory.Demographic,
                    "sum-field": True,
                    "pct-base": "vap_total",
                },
            },
            "geo-fields": {
                "vtdid": {
                    "layer": assign_layer.id(),
                    "field": "vtdid",
                    "caption": "VTD",
                    "category": FieldCategory.Geography,
                }
            },
            "metrics": {
                "metrics": {
                    "total-population": {"value": 227036},
                    "cea_proj": None,
                    "plan-deviation": {"value": [100, -500]},
                    "deviation": None,
                    "pct-deviation": None,
                    "polsbypopper": None,
                    "mean-polsbypopper": {"value": 0.4},
                    "min-polsbypopper": {"value": 0.15},
                    "max-polsbypopper": {"value": 0.8},
                    "agg-polsbypopper": None,
                    "reock": None,
                    "mean-reock": {"value": 0.5},
                    "min-reock": {"value": 0.1},
                    "max-reock": {"value": 0.9},
                    "agg-reock": None,
                    "convexhull": None,
                    "mean-convexhull": {"value": 0.5},
                    "min-convexhull": {"value": 0.1},
                    "max-convexhull": {"value": 0.9},
                    "agg-convexhull": None,
                    "cut-edges": {},
                    "contiguity": {"value": True},
                    "complete": {"value": True},
                    "splits": {
                        "value": {
                            "vtdid": {
                                "field": "vtdid",
                                "caption": "VTD",
                                "data": {
                                    "schema": {
                                        "fields": [{"name": "index", "type": "integer"}],
                                        "primaryKey": ["index"],
                                        "pandas_version": "1.4.0",
                                    },
                                    "data": [],
                                },
                            }
                        }
                    },
                }
            },
        }

    def test_deserialize(self, block_layer, assign_layer, dist_layer):
        data = {
            "id": "6f17839d-5adc-458a-9f4b-fe88ecfc2069",
            "name": "test",
            "description": "",
            "num-districts": 5,
            "num-seats": 5,
            "deviation": 0.025,
            "deviation-type": DeviationType.OverUnder,
            "geo-layer": block_layer.id(),
            "geo-join-field": "geoid",
            "pop-layer": block_layer.id(),
            "pop-join-field": "geoid",
            "pop-field": "pop_total",
            "pop-fields": {
                "vap_total": {
                    "layer": block_layer.id(),
                    "field": "vap_total",
                    "caption": "VAP",
                    "category": FieldCategory.Population,
                }
            },
            "assign-layer": assign_layer.id(),
            "geo-id-field": "geoid",
            "geo-id-caption": "Block",
            "dist-layer": dist_layer.id(),
            "dist-field": "district",
            "data-fields": {
                "vap_ap_black": {
                    "layer": block_layer.id(),
                    "field": "vap_ap_black",
                    "caption": "APBVAP",
                    "category": FieldCategory.Demographic,
                    "sum-field": True,
                    "pct-base": "vap_total",
                },
                "vap_nh_white": {
                    "layer": block_layer.id(),
                    "field": "vap_nh_white",
                    "caption": "WVAP",
                    "category": FieldCategory.Demographic,
                    "sum-field": True,
                    "pct-base": "vap_total",
                },
                "vap_hispanic": {
                    "layer": block_layer.id(),
                    "field": "vap_hispanic",
                    "caption": "HVAP",
                    "category": FieldCategory.Demographic,
                    "sum-field": True,
                    "pct-base": "vap_total",
                },
            },
            "geo-fields": {
                "vtdid": {
                    "layer": assign_layer.id(),
                    "field": "vtdid",
                    "caption": "VTD",
                    "category": FieldCategory.Geography,
                }
            },
            "metrics": {
                "metrics": {
                    "total-population": {"value": 227036},
                    "splits": {
                        "value": {
                            "vtdid": {
                                "field": "vtdid",
                                "data": {
                                    "schema": {
                                        "fields": [{"name": "index", "type": "integer"}],
                                        "primaryKey": ["index"],
                                        "pandas_version": "0.20.0",
                                    },
                                    "data": [],
                                },
                            }
                        }
                    },
                }
            },
        }
        plan = deserialize(RdsPlan, data)
        assert str(plan.id) == "6f17839d-5adc-458a-9f4b-fe88ecfc2069"
        assert plan.name == "test"
        assert plan.numDistricts == 5
        assert plan.numSeats == 5
        assert plan.deviation == 0.025
        assert plan.geoLayer == block_layer
        assert plan.geoJoinField == "geoid"
        assert plan.popLayer == block_layer
        assert plan.popJoinField == "geoid"
        assert plan.geoIdField == "geoid"
        assert plan.geoIdCaption == "Block"
        assert plan.popField == "pop_total"
        assert plan.assignLayer == assign_layer
        assert plan.distLayer == dist_layer
        assert plan.totalPopulation == 227036
        assert len(plan.geoFields) == 1
        assert plan.geoFields[0].field == "vtdid"
        assert plan.geoFields[0].layer == assign_layer
        assert plan.geoFields[0].caption == "VTD"
        assert plan.geoFields[0].category == FieldCategory.Geography
        assert len(plan.dataFields) == 3
        assert len(plan.popFields) == 1
        assert plan.metrics.cutEdges is None
        assert len(plan.metrics.splits) == 1
        assert "vtdid" in plan.metrics.splits
        assert plan.metrics.splits["vtdid"].field == "vtdid"
        assert plan.metrics.splits["vtdid"].data is not None
        assert plan.metrics.splits["vtdid"].data.empty

    def test_validate_district(self, plan: RdsPlan, mocker):
        plan.metrics["totalPopulation"]._value = 500
        plan.deviation = 0.05

        district = mocker.create_autospec(spec=RdsDistrict)
        district.members = 1

        district.population = 100
        assert plan.isDistrictValid(district)

        district.population = 105
        assert plan.isDistrictValid(district)

        district.population = 95
        assert plan.isDistrictValid(district)

        district.population = 106
        assert not plan.isDistrictValid(district)

        district.population = 94
        assert not plan.isDistrictValid(district)

        plan.deviation = 0
        district.population = 100
        assert plan.isDistrictValid(district)

    def test_validate_district_multi_member(self, plan: RdsPlan, mocker):
        plan.metrics["totalPopulation"]._value = 500
        plan.numDistricts = 5
        plan.numSeats = 5
        plan.deviation = 0.05

        district = mocker.create_autospec(spec=RdsDistrict)
        district.members = 2

        district.population = 200
        assert plan.isDistrictValid(district)

        district.population = 210
        assert plan.isDistrictValid(district)

        district.population = 190
        assert plan.isDistrictValid(district)

        district.population = 211
        assert not plan.isDistrictValid(district)

        district.population = 189
        assert not plan.isDistrictValid(district)

        plan.deviation = 0
        district.population = 200
        assert plan.isDistrictValid(district)
