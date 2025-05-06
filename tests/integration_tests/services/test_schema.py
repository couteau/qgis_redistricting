import json

import pandas as pd
import pytest
from packaging import version
from qgis.core import QgsProject, QgsVectorLayer

from redistricting.services.schema import checkMigrateSchema


@pytest.mark.parametrize("plugin_version", ("0.0.1", "0.0.4"))
class TestSchema:
    @pytest.fixture
    def dist_layer(self, plugin_version, datadir):
        gpkg = datadir / f"Test_Plan_v{plugin_version.replace('.', '_')}.gpkg"
        layer = QgsVectorLayer(f"{str(gpkg)}|layer=districts", "districts", "OGR")
        QgsProject.instance().addMapLayer(layer, False)
        return layer

    @pytest.fixture
    def assign_layer(self, plugin_version, datadir):
        gpkg = datadir / f"Test_v{plugin_version.replace('.', '_')}.gpkg"
        layer = QgsVectorLayer(f"{str(gpkg)}|layer=assignments", "assignments", "OGR")
        QgsProject.instance().addMapLayer(layer, False)
        return layer

    @pytest.fixture
    def schema_version(self, plugin_version):
        schema_versions = {"0.0.1": "1.0.0", "0.0.2": "1.0.0", "0.0.3": "1.0.0", "0.0.4": "1.0.1"}
        return schema_versions[plugin_version]

    @pytest.fixture
    def expected_splits(self, schema_version):
        expected = {
            "1.0.0": {
                "census_place": {
                    "data": {
                        "data": [],
                        "schema": {
                            "fields": [
                                {
                                    "name": "census_place",
                                    "type": "string",
                                },
                                {
                                    "name": "district",
                                    "type": "string",
                                },
                                {
                                    "name": "pop_total",
                                    "type": "string",
                                },
                                {
                                    "name": "vap_total",
                                    "type": "string",
                                },
                                {
                                    "name": "cvap_total",
                                    "type": "string",
                                },
                                {
                                    "name": "pop_ap_black",
                                    "type": "string",
                                },
                                {
                                    "name": "pop_nh_white",
                                    "type": "string",
                                },
                                {
                                    "name": "pop_hispanic",
                                    "type": "string",
                                },
                                {
                                    "name": "vap_ap_black",
                                    "type": "string",
                                },
                                {
                                    "name": "vap_nh_white",
                                    "type": "string",
                                },
                                {
                                    "name": "vap_hispanic",
                                    "type": "string",
                                },
                                {
                                    "name": "cvap_ap_black",
                                    "type": "string",
                                },
                                {
                                    "name": "cvap_white",
                                    "type": "string",
                                },
                                {
                                    "name": "cvap_hispanic",
                                    "type": "string",
                                },
                            ],
                            "pandas_version": "1.4.0" if pd.__version__ >= "1.4" else "0.20.0",
                            "primaryKey": [
                                "census_place",
                                "district",
                            ],
                        },
                    },
                    "field": "census_place",
                },
                "vtdid": {
                    "data": {
                        "data": [],
                        "schema": {
                            "fields": [
                                {
                                    "name": "vtdid",
                                    "type": "string",
                                },
                                {
                                    "name": "district",
                                    "type": "string",
                                },
                                {
                                    "name": "pop_total",
                                    "type": "string",
                                },
                                {
                                    "name": "vap_total",
                                    "type": "string",
                                },
                                {
                                    "name": "cvap_total",
                                    "type": "string",
                                },
                                {
                                    "name": "pop_ap_black",
                                    "type": "string",
                                },
                                {
                                    "name": "pop_nh_white",
                                    "type": "string",
                                },
                                {
                                    "name": "pop_hispanic",
                                    "type": "string",
                                },
                                {
                                    "name": "vap_ap_black",
                                    "type": "string",
                                },
                                {
                                    "name": "vap_nh_white",
                                    "type": "string",
                                },
                                {
                                    "name": "vap_hispanic",
                                    "type": "string",
                                },
                                {
                                    "name": "cvap_ap_black",
                                    "type": "string",
                                },
                                {
                                    "name": "cvap_white",
                                    "type": "string",
                                },
                                {
                                    "name": "cvap_hispanic",
                                    "type": "string",
                                },
                            ],
                            "pandas_version": "1.4.0" if pd.__version__ >= "1.4" else "0.20.0",
                            "primaryKey": [
                                "vtdid",
                                "district",
                            ],
                        },
                    },
                    "field": "vtdid",
                },
            },
            "1.0.1": {
                "census_place": {
                    "data": {
                        "data": [
                            {
                                "census_place": "0112516312",
                                "cvap_ap_black": 23.9815638388,
                                "cvap_hispanic": 0.8510638298,
                                "cvap_total": 472.8268004501,
                                "cvap_white": 566.218960712,
                                "district": 5,
                                "pop_ap_black": 20,
                                "pop_hispanic": 24,
                                "pop_nh_white": 631,
                                "pop_total": 686,
                                "vap_ap_black": 17,
                                "vap_hispanic": 13,
                                "vap_nh_white": 488,
                                "vap_total": 525,
                            },
                            {
                                "census_place": "0112516312",
                                "cvap_ap_black": 0.5870841487,
                                "cvap_hispanic": 1.5563380282,
                                "cvap_total": 135.2971354886,
                                "cvap_white": 138.7364093116,
                                "district": 4,
                                "pop_ap_black": 10,
                                "pop_hispanic": 8,
                                "pop_nh_white": 185,
                                "pop_total": 218,
                                "vap_ap_black": 8,
                                "vap_hispanic": 6,
                                "vap_nh_white": 152,
                                "vap_total": 175,
                            },
                            {
                                "census_place": "0112517704",
                                "cvap_ap_black": 633.1009847797,
                                "cvap_hispanic": 7.9392764858,
                                "cvap_total": 1265.9940973323,
                                "cvap_white": 763.7445951763,
                                "district": 1,
                                "pop_ap_black": 808,
                                "pop_hispanic": 118,
                                "pop_nh_white": 1007,
                                "pop_total": 2011,
                                "vap_ap_black": 568,
                                "vap_hispanic": 71,
                                "vap_nh_white": 857,
                                "vap_total": 1561,
                            },
                            {
                                "census_place": "0112517704",
                                "cvap_ap_black": 899.7327302632,
                                "cvap_hispanic": 30.1639344262,
                                "cvap_total": 1199.0420460007,
                                "cvap_white": 470.5690989128,
                                "district": 3,
                                "pop_ap_black": 292,
                                "pop_hispanic": 198,
                                "pop_nh_white": 602,
                                "pop_total": 1119,
                                "vap_ap_black": 199,
                                "vap_hispanic": 123,
                                "vap_nh_white": 513,
                                "vap_total": 859,
                            },
                            {
                                "census_place": "0112535704",
                                "cvap_ap_black": 3.0463576159,
                                "cvap_hispanic": 1.7518248175,
                                "cvap_total": 8.7185725872,
                                "cvap_white": 2.1987951807,
                                "district": 2,
                                "pop_ap_black": 6,
                                "pop_hispanic": 4,
                                "pop_nh_white": 2,
                                "pop_total": 12,
                                "vap_ap_black": 4,
                                "vap_hispanic": 4,
                                "vap_nh_white": 2,
                                "vap_total": 10,
                            },
                            {
                                "census_place": "0112535704",
                                "cvap_ap_black": 1827.6114632305,
                                "cvap_hispanic": 79.4427294955,
                                "cvap_total": 2464.8620396353,
                                "cvap_white": 1021.1292841133,
                                "district": 1,
                                "pop_ap_black": 1847,
                                "pop_hispanic": 563,
                                "pop_nh_white": 958,
                                "pop_total": 3401,
                                "vap_ap_black": 1369,
                                "vap_hispanic": 339,
                                "vap_nh_white": 822,
                                "vap_total": 2558,
                            },
                            {
                                "census_place": "0112555200",
                                "cvap_ap_black": 1365.6128415329,
                                "cvap_hispanic": 70.8339005137,
                                "cvap_total": 9700.1290744052,
                                "cvap_white": 8571.4990271927,
                                "district": 4,
                                "pop_ap_black": 1893,
                                "pop_hispanic": 565,
                                "pop_nh_white": 10660,
                                "pop_total": 13575,
                                "vap_ap_black": 1397,
                                "vap_hispanic": 360,
                                "vap_nh_white": 7886,
                                "vap_total": 9964,
                            },
                            {
                                "census_place": "0112555200",
                                "cvap_ap_black": 3526.5820753304,
                                "cvap_hispanic": 105.8057040998,
                                "cvap_total": 6742.4313566228,
                                "cvap_white": 4201.6369133523,
                                "district": 2,
                                "pop_ap_black": 2831,
                                "pop_hispanic": 547,
                                "pop_nh_white": 4029,
                                "pop_total": 7736,
                                "vap_ap_black": 1928,
                                "vap_hispanic": 333,
                                "vap_nh_white": 3401,
                                "vap_total": 5921,
                            },
                            {
                                "census_place": "0112555200",
                                "cvap_ap_black": 3426.4748999277,
                                "cvap_hispanic": 48.3431498079,
                                "cvap_total": 7251.8554753442,
                                "cvap_white": 4748.0961651015,
                                "district": 5,
                                "pop_ap_black": 3370,
                                "pop_hispanic": 941,
                                "pop_nh_white": 5187,
                                "pop_total": 9814,
                                "vap_ap_black": 2332,
                                "vap_hispanic": 590,
                                "vap_nh_white": 4514,
                                "vap_total": 7662,
                            },
                            {
                                "census_place": "0112577256",
                                "cvap_ap_black": 20187.2825546828,
                                "cvap_hispanic": 216.4808768657,
                                "cvap_total": 18755.403825714,
                                "cvap_white": 3461.5146569498,
                                "district": 5,
                                "pop_ap_black": 18290,
                                "pop_hispanic": 807,
                                "pop_nh_white": 4212,
                                "pop_total": 23711,
                                "vap_ap_black": 13852,
                                "vap_hispanic": 546,
                                "vap_nh_white": 3875,
                                "vap_total": 18614,
                            },
                            {
                                "census_place": "0112577256",
                                "cvap_ap_black": 12097.0796906192,
                                "cvap_hispanic": 378.4721303317,
                                "cvap_total": 16222.7133201767,
                                "cvap_white": 6040.5704199509,
                                "district": 3,
                                "pop_ap_black": 11287,
                                "pop_hispanic": 537,
                                "pop_nh_white": 5573,
                                "pop_total": 17891,
                                "vap_ap_black": 8482,
                                "vap_hispanic": 374,
                                "vap_nh_white": 4955,
                                "vap_total": 14232,
                            },
                            {
                                "census_place": "0112577256",
                                "cvap_ap_black": 445.9479814579,
                                "cvap_hispanic": 72.7703342109,
                                "cvap_total": 6378.945439783,
                                "cvap_white": 5795.0461247407,
                                "district": 4,
                                "pop_ap_black": 481,
                                "pop_hispanic": 293,
                                "pop_nh_white": 6388,
                                "pop_total": 7843,
                                "vap_ap_black": 352,
                                "vap_hispanic": 166,
                                "vap_nh_white": 4759,
                                "vap_total": 5738,
                            },
                            {
                                "census_place": "0112577256",
                                "cvap_ap_black": 8208.2397075051,
                                "cvap_hispanic": 1510.3440510651,
                                "cvap_total": 32030.4029420109,
                                "cvap_white": 23287.3411014471,
                                "district": 2,
                                "pop_ap_black": 7689,
                                "pop_hispanic": 3240,
                                "pop_nh_white": 25383,
                                "pop_total": 38397,
                                "vap_ap_black": 6261,
                                "vap_hispanic": 2967,
                                "vap_nh_white": 23415,
                                "vap_total": 34471,
                            },
                            {
                                "census_place": "0112577256",
                                "cvap_ap_black": 5034.1110280647,
                                "cvap_hispanic": 286.6303774028,
                                "cvap_total": 10363.9241982991,
                                "cvap_white": 6060.1445450205,
                                "district": 1,
                                "pop_ap_black": 4571,
                                "pop_hispanic": 561,
                                "pop_nh_white": 6107,
                                "pop_total": 11758,
                                "vap_ap_black": 3422,
                                "vap_hispanic": 405,
                                "vap_nh_white": 5438,
                                "vap_total": 9708,
                            },
                        ],
                        "schema": {
                            "fields": [
                                {
                                    "name": "census_place",
                                    "type": "string",
                                },
                                {
                                    "name": "district",
                                    "type": "integer",
                                },
                                {
                                    "name": "pop_total",
                                    "type": "integer",
                                },
                                {
                                    "name": "vap_total",
                                    "type": "integer",
                                },
                                {
                                    "name": "cvap_total",
                                    "type": "number",
                                },
                                {
                                    "name": "pop_ap_black",
                                    "type": "integer",
                                },
                                {
                                    "name": "pop_nh_white",
                                    "type": "integer",
                                },
                                {
                                    "name": "pop_hispanic",
                                    "type": "integer",
                                },
                                {
                                    "name": "vap_ap_black",
                                    "type": "integer",
                                },
                                {
                                    "name": "vap_nh_white",
                                    "type": "integer",
                                },
                                {
                                    "name": "vap_hispanic",
                                    "type": "integer",
                                },
                                {
                                    "name": "cvap_ap_black",
                                    "type": "number",
                                },
                                {
                                    "name": "cvap_white",
                                    "type": "number",
                                },
                                {
                                    "name": "cvap_hispanic",
                                    "type": "number",
                                },
                            ],
                            "pandas_version": "1.4.0" if pd.__version__ >= "1.4" else "0.20.0",
                            "primaryKey": [
                                "census_place",
                                "district",
                            ],
                        },
                    },
                    "field": "census_place",
                },
                "vtdid": {
                    "data": {
                        "data": [
                            {
                                "cvap_ap_black": 1937.3336631958,
                                "cvap_hispanic": 45.2816901408,
                                "cvap_total": 3691.5632883837,
                                "cvap_white": 2505.0263437648,
                                "district": 5,
                                "pop_ap_black": 1713,
                                "pop_hispanic": 673,
                                "pop_nh_white": 3060,
                                "pop_total": 5681,
                                "vap_ap_black": 1118,
                                "vap_hispanic": 431,
                                "vap_nh_white": 2562,
                                "vap_total": 4265,
                                "vtdid": "01125000020",
                            },
                            {
                                "cvap_ap_black": 0.0,
                                "cvap_hispanic": 0.0,
                                "cvap_total": 0.0,
                                "cvap_white": 0.0,
                                "district": 4,
                                "pop_ap_black": 2,
                                "pop_hispanic": 3,
                                "pop_nh_white": 0,
                                "pop_total": 3,
                                "vap_ap_black": 0,
                                "vap_hispanic": 0,
                                "vap_nh_white": 0,
                                "vap_total": 0,
                                "vtdid": "01125000020",
                            },
                        ],
                        "schema": {
                            "fields": [
                                {
                                    "name": "vtdid",
                                    "type": "string",
                                },
                                {
                                    "name": "district",
                                    "type": "integer",
                                },
                                {
                                    "name": "pop_total",
                                    "type": "integer",
                                },
                                {
                                    "name": "vap_total",
                                    "type": "integer",
                                },
                                {
                                    "name": "cvap_total",
                                    "type": "number",
                                },
                                {
                                    "name": "pop_ap_black",
                                    "type": "integer",
                                },
                                {
                                    "name": "pop_nh_white",
                                    "type": "integer",
                                },
                                {
                                    "name": "pop_hispanic",
                                    "type": "integer",
                                },
                                {
                                    "name": "vap_ap_black",
                                    "type": "integer",
                                },
                                {
                                    "name": "vap_nh_white",
                                    "type": "integer",
                                },
                                {
                                    "name": "vap_hispanic",
                                    "type": "integer",
                                },
                                {
                                    "name": "cvap_ap_black",
                                    "type": "number",
                                },
                                {
                                    "name": "cvap_white",
                                    "type": "number",
                                },
                                {
                                    "name": "cvap_hispanic",
                                    "type": "number",
                                },
                            ],
                            "pandas_version": "1.4.0" if pd.__version__ >= "1.4" else "0.20.0",
                            "primaryKey": [
                                "vtdid",
                                "district",
                            ],
                        },
                    },
                    "field": "vtdid",
                },
            },
        }

        return expected[schema_version]

    @pytest.fixture
    def json_str(self, schema_version, block_layer, dist_layer, assign_layer):
        json_strs = {
            "1.0.0": f"""
                {{
                    "id": "8b37437d-b7b4-40a8-a8ba-42c19d6ee10a",
                    "name": "Test Plan v0.0.1",
                    "description": "Plan created using plugin release 0.0.1-alpha",
                    "total-population": 227036,
                    "num-districts": 5,
                    "deviation": 0.05,
                    "pop-layer": "{block_layer.id()}",
                    "assign-layer": "{assign_layer.id()}",
                    "dist-layer": "{dist_layer.id()}",
                    "geo-id-field": "geoid",
                    "geo-id-display": "Block",
                    "dist-field": "district",
                    "pop-field": "pop_total",
                    "vap-field": "vap_total",
                    "cvap-field": "cvap_total",
                    "data-fields": [
                        {{"layer": "{block_layer.id()}", "field": "pop_ap_black", "expression": false,
                                                    "caption": "AP Black", "sum": true, "pctbase": 1}},
                        {{"layer": "{block_layer.id()}", "field": "pop_nh_white", "expression": false,
                                                    "caption": "White", "sum": true, "pctbase": 1}},
                        {{"layer": "{block_layer.id()}", "field": "pop_hispanic", "expression": false,
                                                    "caption": "Hispanic", "sum": true, "pctbase": 1}},
                        {{"layer": "{block_layer.id()}", "field": "vap_ap_black", "expression": false,
                                                    "caption": "APBVAP", "sum": true, "pctbase": 2}},
                        {{"layer": "{block_layer.id()}", "field": "vap_nh_white", "expression": false,
                                                    "caption": "WVAP", "sum": true, "pctbase": 2}},
                        {{"layer": "{block_layer.id()}", "field": "vap_hispanic", "expression": false,
                                                    "caption": "HVAP", "sum": true, "pctbase": 2}},
                        {{"layer": "{block_layer.id()}", "field": "cvap_ap_black", "expression": false,
                                                    "caption": "BCVAP", "sum": true, "pctbase": 3}},
                        {{"layer": "{block_layer.id()}", "field": "cvap_white", "expression": false,
                                                    "caption": "WCVAP", "sum": true, "pctbase": 3}},
                        {{"layer": "{block_layer.id()}", "field": "cvap_hispanic", "expression": false,
                                                    "caption": "HCVAP", "sum": true, "pctbase": 3}}
                    ],
                    "geo-fields": [
                        {{"layer": "{block_layer.id()}", "field": "vtdid", "expression": false, "caption": "Precinct/VTD"}},
                        {{"layer": "{block_layer.id()}", "field": "statefp || countyfp || place",
                                                    "expression": true, "caption": "Census Place"}}
                    ],
                    "districts": [
                        {{"district": 1, "name": "1", "description": "", "members": 1}},
                        {{"district": 2, "name": "2", "description": "", "members": 1}},
                        {{"district": 3, "name": "3", "description": "", "members": 1}},
                        {{"district": 4, "name": "4", "description": "", "members": 1}},
                        {{"district": 5, "name": "5", "description": "", "members": 1}}
                    ],
                    "plan-stats": {{
                        "cut-edges": 0,
                        "splits": {{
                            "vtdid": [["01125000020", 2]],
                            "census_place": [["0112516312", 2], ["0112517704", 2], ["0112535704", 2], ["0112555200", 3], ["0112577256", 5]]
                        }}
                    }}
                }}
            """,
            "1.0.1": f"""
                {{
                    "id": "cec4fe12-41e1-42a9-8120-24d06dc323b5",
                    "name": "Test Plan v0.0.4",
                    "description": "Test plan created with plugin version 0.0.4-alpha",
                    "total-population": 227036,
                    "num-districts": 5,
                    "deviation": 0.05,
                    "pop-layer": "{block_layer.id()}",
                    "assign-layer": "{assign_layer.id()}",
                    "geo-id-field": "geoid",
                    "geo-id-caption": "Block",
                    "dist-field": "district",
                    "geo-fields": [
                        {{"layer": "{block_layer.id()}", "field": "vtdid", "expression": false, "caption": "Precinct/VTD"}},
                        {{"layer": "{block_layer.id()}", "field": "statefp || countyfp || place",
                                                    "expression": true, "caption": "Census Place"}}
                    ],
                    "dist-layer": "{dist_layer.id()}",
                    "pop-field": "pop_total",
                    "pop-fields": [
                        {{"layer": "{block_layer.id()}", "field": "vap_total", "expression": false, "caption": "VAP"}},
                        {{"layer": "{block_layer.id()}", "field": "cvap_total", "expression": false, "caption": "CVAP"}}
                    ],
                    "data-fields": [
                        {{"layer": "{block_layer.id()}", "field": "pop_ap_black", "expression": false,
                                                    "caption": "AP Black", "sum": true, "pctbase": "pop_total"}},
                        {{"layer": "{block_layer.id()}", "field": "pop_nh_white", "expression": false,
                                                    "caption": "White", "sum": true, "pctbase": "pop_total"}},
                        {{"layer": "{block_layer.id()}", "field": "pop_hispanic", "expression": false,
                                                    "caption": "Hispanic", "sum": true, "pctbase": "pop_total"}},
                        {{"layer": "{block_layer.id()}", "field": "vap_ap_black", "expression": false,
                                                    "caption": "APBVAP", "sum": true, "pctbase": "vap_total"}},
                        {{"layer": "{block_layer.id()}", "field": "vap_nh_white", "expression": false,
                                                    "caption": "WVAP", "sum": true, "pctbase": "vap_total"}},
                        {{"layer": "{block_layer.id()}", "field": "vap_hispanic", "expression": false,
                                                    "caption": "HVAP", "sum": true, "pctbase": "vap_total"}},
                        {{"layer": "{block_layer.id()}", "field": "cvap_ap_black", "expression": false,
                                                    "caption": "BCVAP", "sum": true, "pctbase": "cvap_total"}},
                        {{"layer": "{block_layer.id()}", "field": "cvap_white", "expression": false,
                                                    "caption": "WCVAP", "sum": true, "pctbase": "cvap_total"}},
                        {{"layer": "{block_layer.id()}", "field": "cvap_hispanic", "expression": false,
                                                    "caption": "HCVAP", "sum": true, "pctbase": "cvap_total"}}
                    ],
                    "districts": [
                        {{"district": 1, "name": "1", "description": "", "members": 1}},
                        {{"district": 2, "name": "2", "description": "", "members": 1}},
                        {{"district": 3, "name": "3", "description": "", "members": 1}},
                        {{"district": 4, "name": "4", "description": "", "members": 1}},
                        {{"district": 5, "name": "5", "description": "", "members": 1}}
                    ],
                    "plan-stats": {{
                        "cut-edges": 0,
                        "splits": {{
                            "vtdid": [
                                {{
                                    "vtdid": "01125000020",
                                    "districts": {{
                                        "5": {{"pop_total": 5681, "vap_total": 4265, "cvap_total": 3691.5632883837143, "pop_ap_black": 1713, "pop_nh_white": 3060, "pop_hispanic": 673, "vap_ap_black": 1118, "vap_nh_white": 2562, "vap_hispanic": 431, "cvap_ap_black": 1937.3336631958043, "cvap_white": 2505.0263437647977, "cvap_hispanic": 45.28169014084507}},
                                        "4": {{"pop_total": 3, "vap_total": 0, "cvap_total": 0.0, "pop_ap_black": 2, "pop_nh_white": 0, "pop_hispanic": 3, "vap_ap_black": 0, "vap_nh_white": 0, "vap_hispanic": 0, "cvap_ap_black": 0.0, "cvap_white": 0.0, "cvap_hispanic": 0.0}}
                                    }},
                                    "splits": 2}}
                            ],
                            "census_place": [
                                {{
                                    "census_place": "0112516312",
                                    "districts": {{
                                        "5": {{"pop_total": 686, "vap_total": 525, "cvap_total": 472.82680045011256, "pop_ap_black": 20, "pop_nh_white": 631, "pop_hispanic": 24, "vap_ap_black": 17, "vap_nh_white": 488, "vap_hispanic": 13, "cvap_ap_black": 23.981563838821508, "cvap_white": 566.2189607120381, "cvap_hispanic": 0.851063829787234}},
                                        "4": {{"pop_total": 218, "vap_total": 175, "cvap_total": 135.29713548862486, "pop_ap_black": 10, "pop_nh_white": 185, "pop_hispanic": 8, "vap_ap_black": 8, "vap_nh_white": 152, "vap_hispanic": 6, "cvap_ap_black": 0.5870841487279843, "cvap_white": 138.7364093116297, "cvap_hispanic": 1.556338028169014}}
                                    }},
                                    "splits": 2
                                }},
                                {{
                                    "census_place": "0112517704",
                                    "districts": {{
                                        "1": {{"pop_total": 2011, "vap_total": 1561, "cvap_total": 1265.9940973322696, "pop_ap_black": 808, "pop_nh_white": 1007, "pop_hispanic": 118, "vap_ap_black": 568, "vap_nh_white": 857, "vap_hispanic": 71, "cvap_ap_black": 633.1009847797474, "cvap_white": 763.744595176337, "cvap_hispanic": 7.939276485788113}},
                                        "3": {{"pop_total": 1119, "vap_total": 859, "cvap_total": 1199.0420460007351, "pop_ap_black": 292, "pop_nh_white": 602, "pop_hispanic": 198, "vap_ap_black": 199, "vap_nh_white": 513, "vap_hispanic": 123, "cvap_ap_black": 899.7327302631579, "cvap_white": 470.569098912826, "cvap_hispanic": 30.16393442622951}}
                                    }},
                                    "splits": 2
                                }},
                                {{
                                    "census_place": "0112535704",
                                    "districts": {{
                                        "2": {{"pop_total": 12, "vap_total": 10, "cvap_total": 8.718572587185726, "pop_ap_black": 6, "pop_nh_white": 2, "pop_hispanic": 4, "vap_ap_black": 4, "vap_nh_white": 2, "vap_hispanic": 4, "cvap_ap_black": 3.0463576158940397, "cvap_white": 2.1987951807228914, "cvap_hispanic": 1.7518248175182483}},
                                        "1": {{"pop_total": 3401, "vap_total": 2558, "cvap_total": 2464.8620396352826, "pop_ap_black": 1847, "pop_nh_white": 958, "pop_hispanic": 563, "vap_ap_black": 1369, "vap_nh_white": 822, "vap_hispanic": 339, "cvap_ap_black": 1827.6114632305032, "cvap_white": 1021.1292841133474, "cvap_hispanic": 79.44272949552335}}
                                    }},
                                    "splits": 2
                                }},
                                {{
                                    "census_place": "0112555200",
                                    "districts": {{
                                        "4": {{"pop_total": 13575, "vap_total": 9964, "cvap_total": 9700.129074405188, "pop_ap_black": 1893, "pop_nh_white": 10660, "pop_hispanic": 565, "vap_ap_black": 1397, "vap_nh_white": 7886, "vap_hispanic": 360, "cvap_ap_black": 1365.6128415329497, "cvap_white": 8571.499027192689, "cvap_hispanic": 70.83390051372363}},
                                        "2": {{"pop_total": 7736, "vap_total": 5921, "cvap_total": 6742.4313566228, "pop_ap_black": 2831, "pop_nh_white": 4029, "pop_hispanic": 547, "vap_ap_black": 1928, "vap_nh_white": 3401, "vap_hispanic": 333, "cvap_ap_black": 3526.5820753304106, "cvap_white": 4201.636913352274, "cvap_hispanic": 105.80570409982175}},
                                        "5": {{"pop_total": 9814, "vap_total": 7662, "cvap_total": 7251.85547534416, "pop_ap_black": 3370, "pop_nh_white": 5187, "pop_hispanic": 941, "vap_ap_black": 2332, "vap_nh_white": 4514, "vap_hispanic": 590, "cvap_ap_black": 3426.4748999277053, "cvap_white": 4748.096165101506, "cvap_hispanic": 48.34314980793854}}
                                    }},
                                    "splits": 3
                                }},
                                {{
                                    "census_place": "0112577256",
                                    "districts": {{
                                        "5": {{"pop_total": 23711, "vap_total": 18614, "cvap_total": 18755.403825714024, "pop_ap_black": 18290, "pop_nh_white": 4212, "pop_hispanic": 807, "vap_ap_black": 13852, "vap_nh_white": 3875, "vap_hispanic": 546, "cvap_ap_black": 20187.282554682795, "cvap_white": 3461.514656949821, "cvap_hispanic": 216.48087686567163}},
                                        "3": {{"pop_total": 17891, "vap_total": 14232, "cvap_total": 16222.713320176737, "pop_ap_black": 11287, "pop_nh_white": 5573, "pop_hispanic": 537, "vap_ap_black": 8482, "vap_nh_white": 4955, "vap_hispanic": 374, "cvap_ap_black": 12097.07969061923, "cvap_white": 6040.570419950905, "cvap_hispanic": 378.4721303317455}},
                                        "4": {{"pop_total": 7843, "vap_total": 5738, "cvap_total": 6378.945439783049, "pop_ap_black": 481, "pop_nh_white": 6388, "pop_hispanic": 293, "vap_ap_black": 352, "vap_nh_white": 4759, "vap_hispanic": 166, "cvap_ap_black": 445.94798145792345, "cvap_white": 5795.046124740686, "cvap_hispanic": 72.77033421094548}},
                                        "2": {{"pop_total": 38397, "vap_total": 34471, "cvap_total": 32030.402942010907, "pop_ap_black": 7689, "pop_nh_white": 25383, "pop_hispanic": 3240, "vap_ap_black": 6261, "vap_nh_white": 23415, "vap_hispanic": 2967, "cvap_ap_black": 8208.23970750512, "cvap_white": 23287.3411014471, "cvap_hispanic": 1510.3440510650776}},
                                        "1": {{"pop_total": 11758, "vap_total": 9708, "cvap_total": 10363.924198299104, "pop_ap_black": 4571, "pop_nh_white": 6107, "pop_hispanic": 561, "vap_ap_black": 3422, "vap_nh_white": 5438, "vap_hispanic": 405, "cvap_ap_black": 5034.111028064659, "cvap_white": 6060.144545020535, "cvap_hispanic": 286.6303774028019}}
                                    }},
                                    "splits": 5
                                }}
                            ]
                        }}
                    }}
                }}
            """,
        }

        return json_strs[schema_version]

    def test_migrate(  # noqa: PLR0913
        self, schema_version, json_str, block_layer, expected_splits, assign_layer, dist_layer
    ):
        plan_data = json.loads(json_str)

        migrated = checkMigrateSchema(plan_data, version.parse(schema_version))

        assert migrated == {
            "id": plan_data["id"],
            "name": plan_data["name"],
            "description": plan_data["description"],
            "total-population": 227036,
            "num-districts": 5,
            "deviation": 0.05,
            "assign-layer": assign_layer.id(),
            "dist-layer": dist_layer.id(),
            "geo-id-field": "geoid",
            "geo-id-caption": "Block",
            "geo-layer": block_layer.id(),
            "dist-field": "district",
            "pop-field": "pop_total",
            "pop-fields": [
                {"field": "vap_total", "layer": block_layer.id(), "caption": "VAP"},
                {"field": "cvap_total", "layer": block_layer.id(), "caption": "CVAP"},
            ],
            "data-fields": [
                {
                    "layer": block_layer.id(),
                    "field": "pop_ap_black",
                    "caption": "AP Black",
                    "sum-field": True,
                    "pct-base": "pop_total",
                },
                {
                    "layer": block_layer.id(),
                    "field": "pop_nh_white",
                    "caption": "White",
                    "sum-field": True,
                    "pct-base": "pop_total",
                },
                {
                    "layer": block_layer.id(),
                    "field": "pop_hispanic",
                    "caption": "Hispanic",
                    "sum-field": True,
                    "pct-base": "pop_total",
                },
                {
                    "layer": block_layer.id(),
                    "field": "vap_ap_black",
                    "caption": "APBVAP",
                    "sum-field": True,
                    "pct-base": "vap_total",
                },
                {
                    "layer": block_layer.id(),
                    "field": "vap_nh_white",
                    "caption": "WVAP",
                    "sum-field": True,
                    "pct-base": "vap_total",
                },
                {
                    "layer": block_layer.id(),
                    "field": "vap_hispanic",
                    "caption": "HVAP",
                    "sum-field": True,
                    "pct-base": "vap_total",
                },
                {
                    "layer": block_layer.id(),
                    "field": "cvap_ap_black",
                    "caption": "BCVAP",
                    "sum-field": True,
                    "pct-base": "cvap_total",
                },
                {
                    "layer": block_layer.id(),
                    "field": "cvap_white",
                    "caption": "WCVAP",
                    "sum-field": True,
                    "pct-base": "cvap_total",
                },
                {
                    "layer": block_layer.id(),
                    "field": "cvap_hispanic",
                    "caption": "HCVAP",
                    "sum-field": True,
                    "pct-base": "cvap_total",
                },
            ],
            "geo-fields": [
                {"layer": block_layer.id(), "field": "vtdid", "caption": "Precinct/VTD"},
                {"layer": block_layer.id(), "field": "statefp || countyfp || place", "caption": "Census Place"},
            ],
            "metrics": {
                "complete": True,
                "contiguity": True,
                "cut-edges": 0,
                "max-convexhull": 0.8405175130817178,
                "max-polsbypopper": 0.43852294275692383,
                "max-reock": 0.5144801864093504,
                "mean-convexhull": 0.8172624928403671,
                "mean-polsbypopper": 0.36053023577844356,
                "mean-reock": 0.40459770109520826,
                "min-convexhull": 0.7683134850947537,
                "min-polsbypopper": 0.30061907158011386,
                "min-reock": 0.3017391198900314,
                "plan-deviation": [
                    -0.058078894977007994,
                    0.07064518402367913,
                ],
                "splits": expected_splits,
                "total-population": 227036,
            },
        }
