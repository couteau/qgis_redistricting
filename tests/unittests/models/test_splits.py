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
        return pd.DataFrame.from_dict(
            {
                'index': [
                    ('0116312', 1), ('0116312', 5),
                    ('0135704', 2), ('0135704', 3),
                    ('0155200', 1), ('0155200', 3), ('0155200', 5),
                    ('0177256', 1), ('0177256', 2), ('0177256', 3), ('0177256', 4), ('0177256', 5)
                ],
                'columns': [
                    'population', 'vap_total', 'cvap_total',
                    'pop_ap_black', 'pop_nh_black', 'pop_nh_white', 'pop_hispanic',
                    'vap_ap_black', 'vap_nh_black', 'vap_nh_white', 'vap_hispanic',
                    'cvap_black', 'cvap_white', 'cvap_hispanic', '__name'
                ],
                'data': [
                    [218, 175, 135.29713548862486, 10, 9, 185, 8, 8, 8, 152, 6,
                        0.6392045454545454, 138.7364093116297, 1.556338028169014, 'Coker'],
                    [686, 525, 472.8268004501125, 20, 13, 631, 24, 17, 11, 488, 13,
                        11.968421052631578, 566.2189607120381, 0.851063829787234, 'Coker'],
                    [501, 362, 352.8831229157503, 252, 239, 154, 86, 167, 161, 138, 47,
                        161.84417781297097, 165.7105828632823, 23.4371921182266, 'Holt'],
                    [2912, 2206, 2120.697489306718, 1601, 1543, 806, 481, 1206, 1178, 686,
                        296, 1163.768235017867, 857.6174964307879, 57.757362194815, 'Holt'],
                    [23353, 17562, 17485.7716174201, 4434, 4222, 16605, 1376, 3153, 3053, 12856,
                        883, 2412.626482494558, 14421.326740052353, 141.98275442148392, 'Northport'],
                    [3098, 2152, 2319.743482263867, 1973, 1908, 681, 390, 1262, 1219, 609, 235,
                        1707.3620228766558, 521.6544782826682, 79.72727272727273, 'Northport'],
                    [4674, 3833, 3888.9008066881784, 1687, 1624, 2590, 287, 1242, 1205, 2336, 165,
                        1171.3546978557506, 2578.250887311446, 3.2727272727272725, 'Northport'],
                    [464, 325, 364.232826782868, 40, 21, 360, 32, 19, 11, 267, 17,
                        10.852813852813853, 326.0579895542555, 4.2857142857142865, 'Tuscaloosa'],
                    [13270, 11086, 10828.493513577612, 4769, 4542, 7204, 653, 3620, 3464, 6469, 453,
                        3786.894560780294, 6503.099828570596, 305.29397523516855, 'Tuscaloosa'],
                    [38281, 32639, 33513.06700370153, 7649, 7198, 25184, 3196, 6085, 5775, 21859,
                        2857, 6151.846921250078, 24691.265696660597, 1496.7419995033654, 'Tuscaloosa'],
                    [17316, 13812, 15706.960974809352, 11027, 10734, 5355, 497, 8302, 8120, 4773,
                        358, 9114.127351509875, 5866.333259898235, 371.23852377436845, 'Tuscaloosa'],
                    [30269, 24901, 23338.63540711246, 18833, 18372, 9560, 1060, 14343, 14016, 9074,
                        773, 15577.042696194067, 7257.860073425359, 287.13755707762556, 'Tuscaloosa']
                ],
                'index_names': [None, 'district'],
                'column_names': [None]
            },
            orient="tight"
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
