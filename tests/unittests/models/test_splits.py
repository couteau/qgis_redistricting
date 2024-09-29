import pandas as pd
import pytest

from redistricting.models import (
    RdsGeoField,
    RdsSplitDistrict,
    RdsSplitGeography,
    RdsSplits
)


class TestSplits:
    @pytest.fixture
    def geo_field(self, block_layer):
        return RdsGeoField(block_layer, 'vtdid', 'VTD')

    @pytest.fixture
    def splits_data(self):
        return pd.read_json(
            """{
                "schema": {
                    "fields": [
                        {"name": "geoid", "type": "string"},
                        {"name": "district", "type": "integer"},
                        {"name": "population", "type": "integer"},
                        {"name": "vap_total", "type": "integer"},
                        {"name": "cvap_total", "type": "number"},
                        {"name": "pop_ap_black", "type": "integer"},
                        {"name": "pop_nh_black", "type": "integer"},
                        {"name": "pop_nh_white", "type": "integer"},
                        {"name": "pop_hispanic", "type": "integer"},
                        {"name": "vap_ap_black", "type": "integer"},
                        {"name": "vap_nh_black", "type": "integer"},
                        {"name": "vap_nh_white", "type": "integer"},
                        {"name": "vap_hispanic", "type": "integer"},
                        {"name": "cvap_black", "type": "number"},
                        {"name": "cvap_white", "type": "number"},
                        {"name": "cvap_hispanic", "type": "number"},
                        {"name": "__name", "type": "string"}
                    ],
                    "primaryKey": ["geoid", "district"],
                    "pandas_version": "1.4.0"},
                "data": [
                    {"geoid": "0116312", "district": 1, "population": 218, "vap_total": 175, "cvap_total": 135.29713548862486,
                     "pop_ap_black": 10, "pop_nh_black": 9, "pop_nh_white": 185, "pop_hispanic": 8,
                     "vap_ap_black": 8, "vap_nh_black": 8, "vap_nh_white": 152, "vap_hispanic": 6,
                     "cvap_black": 0.639204545454545, "cvap_white": 138.7364093116297, "cvap_hispanic": 1.556338028169014,
                     "__name": "Coker"},
                    {"geoid": "0116312", "district": 5, "population": 686, "vap_total": 525, "cvap_total": 472.826800450112501,
                     "pop_ap_black": 20, "pop_nh_black": 13, "pop_nh_white": 631, "pop_hispanic": 24,
                     "vap_ap_black": 17, "vap_nh_black": 11, "vap_nh_white": 488, "vap_hispanic": 13,
                     "cvap_black": 11.968421052631578, "cvap_white": 566.218960712038097, "cvap_hispanic": 0.851063829787234,
                     "__name": "Coker"},
                    {"geoid": "0135704", "district": 2, "population": 501, "vap_total": 362, "cvap_total": 352.883122915750278,
                     "pop_ap_black": 252, "pop_nh_black": 239, "pop_nh_white": 154, "pop_hispanic": 86,
                     "vap_ap_black": 167, "vap_nh_black": 161, "vap_nh_white": 138, "vap_hispanic": 47,
                     "cvap_black": 161.844177812970969, "cvap_white": 165.710582863282298, "cvap_hispanic": 23.437192118226601,
                     "__name": "Holt"},
                    {"geoid": "0135704", "district": 3, "population": 2912, "vap_total": 2206, "cvap_total": 2120.697489306718126,
                     "pop_ap_black": 1601, "pop_nh_black": 1543, "pop_nh_white": 806, "pop_hispanic": 481,
                     "vap_ap_black": 1206, "vap_nh_black": 1178, "vap_nh_white": 686, "vap_hispanic": 296,
                     "cvap_black": 1163.768235017867028, "cvap_white": 857.617496430787924, "cvap_hispanic": 57.757362194815002,
                     "__name": "Holt"},
                    {"geoid": "0155200", "district": 1, "population": 23353, "vap_total": 17562, "cvap_total": 17485.771617420101393,
                     "pop_ap_black": 4434, "pop_nh_black": 4222, "pop_nh_white": 16605, "pop_hispanic": 1376,
                     "vap_ap_black": 3153, "vap_nh_black": 3053, "vap_nh_white": 12856, "vap_hispanic": 883,
                     "cvap_black": 2412.626482494557877, "cvap_white": 14421.326740052352761, "cvap_hispanic": 141.982754421483918,
                     "__name": "Northport"},
                    {"geoid": "0155200", "district": 3, "population": 3098, "vap_total": 2152, "cvap_total": 2319.743482263867008,
                     "pop_ap_black": 1973, "pop_nh_black": 1908, "pop_nh_white": 681, "pop_hispanic": 390,
                     "vap_ap_black": 1262, "vap_nh_black": 1219, "vap_nh_white": 609, "vap_hispanic": 235,
                     "cvap_black": 1707.362022876655828, "cvap_white": 521.654478282668151, "cvap_hispanic": 79.727272727272734,
                     "__name": "Northport"},
                    {"geoid": "0155200", "district": 5, "population": 4674, "vap_total": 3833, "cvap_total": 3888.900806688178363,
                     "pop_ap_black": 1687, "pop_nh_black": 1624, "pop_nh_white": 2590, "pop_hispanic": 287,
                     "vap_ap_black": 1242, "vap_nh_black": 1205, "vap_nh_white": 2336, "vap_hispanic": 165,
                     "cvap_black": 1171.354697855750601, "cvap_white": 2578.250887311446149, "cvap_hispanic": 3.272727272727272,
                     "__name": "Northport"},
                    {"geoid": "0177256", "district": 1, "population": 464, "vap_total": 325, "cvap_total": 364.232826782868017,
                     "pop_ap_black": 40, "pop_nh_black": 21, "pop_nh_white": 360, "pop_hispanic": 32,
                     "vap_ap_black": 19, "vap_nh_black": 11, "vap_nh_white": 267, "vap_hispanic": 17,
                     "cvap_black": 10.852813852813853, "cvap_white": 326.057989554255528, "cvap_hispanic": 4.285714285714286,
                     "__name": "Tuscaloosa"},
                    {"geoid": "0177256", "district": 2, "population": 13270, "vap_total": 11086, "cvap_total": 10828.493513577612248,
                     "pop_ap_black": 4769, "pop_nh_black": 4542, "pop_nh_white": 7204, "pop_hispanic": 653,
                     "vap_ap_black": 3620, "vap_nh_black": 3464, "vap_nh_white": 6469, "vap_hispanic": 453,
                     "cvap_black": 3786.894560780293887, "cvap_white": 6503.099828570596401, "cvap_hispanic": 305.293975235168546,
                     "__name": "Tuscaloosa"},
                    {"geoid": "0177256", "district": 3, "population": 38281, "vap_total": 32639, "cvap_total": 33513.067003701529757,
                     "pop_ap_black": 7649, "pop_nh_black": 7198, "pop_nh_white": 25184, "pop_hispanic": 3196,
                     "vap_ap_black": 6085, "vap_nh_black": 5775, "vap_nh_white": 21859, "vap_hispanic": 2857,
                     "cvap_black": 6151.846921250077685, "cvap_white": 24691.265696660597314, "cvap_hispanic": 1496.741999503365378,
                     "__name": "Tuscaloosa"},
                    {"geoid": "0177256", "district": 4, "population": 17316, "vap_total": 13812, "cvap_total": 15706.960974809351683,
                     "pop_ap_black": 11027, "pop_nh_black": 10734, "pop_nh_white": 5355, "pop_hispanic": 497,
                     "vap_ap_black": 8302, "vap_nh_black": 8120, "vap_nh_white": 4773, "vap_hispanic": 358,
                     "cvap_black": 9114.127351509874643, "cvap_white": 5866.333259898235156, "cvap_hispanic": 371.238523774368446,
                     "__name": "Tuscaloosa"},
                    {"geoid": "0177256", "district": 5, "population": 30269, "vap_total": 24901, "cvap_total": 23338.635407112458779,
                     "pop_ap_black": 18833, "pop_nh_black": 18372, "pop_nh_white": 9560, "pop_hispanic": 1060,
                     "vap_ap_black": 14343, "vap_nh_black": 14016, "vap_nh_white": 9074, "vap_hispanic": 773,
                     "cvap_black": 15577.042696194066593, "cvap_white": 7257.860073425358678, "cvap_hispanic": 287.137557077625559,
                     "__name": "Tuscaloosa"}
                ]
            }""",
            orient="table"
        )

    def test_create_splits_no_data(self, geo_field):
        s = RdsSplits(geo_field)
        assert s.geoField == geo_field
        assert s.field == 'vtdid'
        assert isinstance(s.data, pd.DataFrame) and s.data.empty

    def test_create_splits_with_data(self, geo_field, splits_data):
        s = RdsSplits(geo_field, splits_data)
        assert s.geoField == geo_field
        assert s.field == 'vtdid'
        assert isinstance(s.data, pd.DataFrame) and len(s.data) == 12
        assert len(s.splits) == 4
        assert s.attrCount == 16

    def test_create_split_geography(self, geo_field, splits_data):
        s = RdsSplits(geo_field, splits_data)
        g = RdsSplitGeography(s, splits_data, '0155200')
        assert len(g) == 3
        assert g.name == 'Northport'
        assert g.geoid == '0155200'
        assert g.districts == [1, 3, 5]
        assert g.attributes == ['Northport (0155200)', '1, 3, 5']

    def test_create_split_district(self, geo_field, splits_data):
        s = RdsSplits(geo_field, splits_data)
        g = RdsSplitGeography(s, splits_data, '0155200')
        d = RdsSplitDistrict(g, splits_data, ('0155200', 3))
        assert d.geoid == '0155200'
        assert d.district == 3
        assert d.parent == g
        assert len(d) == 15
        assert len(list(d.attributes)) == 15
        assert list(d.attributes) == [3, 3098, 2152, 2319.743482263867, 1973, 1908, 681, 390, 1262, 1219, 609, 235,
                                      1707.3620228766558, 521.6544782826682, 79.72727272727273]
