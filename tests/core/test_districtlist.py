"""QGIS Redistricting Plugin - unit tests for DistrictList class"""
import pytest
from redistricting.core.DistrictList import DistrictList
from redistricting.core.District import District, Unassigned

# pylint: disable=no-self-use


class TestDistrictList:
    @pytest.fixture
    def empty_district_list(self, plan) -> DistrictList:
        return DistrictList(plan)

    @pytest.fixture
    def district_list(self, empty_district_list: DistrictList) -> DistrictList:
        empty_district_list.addDistrict(2, 'District 2')
        return empty_district_list

    @pytest.fixture
    def district(self, district_list: DistrictList) -> District:
        return district_list['2']

    @pytest.fixture
    def unassigned(self, district_list) -> Unassigned:
        return district_list['0']

    def test_create(self, empty_district_list):
        assert len(empty_district_list) == 1
        assert empty_district_list[0].name == 'Unassigned'

    def test_add_district(self, district_list):
        assert len(district_list) == 2
        assert district_list[1].name == 'District 2'

    def test_contains(self, district_list, district):
        assert district in district_list
        assert 2 in district_list
        assert '2' in district_list
        assert 3 not in district_list

    def test_keys(self, district_list):
        assert list(district_list.keys()) == [0, 2]

    def test_values(self, district_list, district, unassigned):
        assert list(district_list.values()) == [unassigned, district]

    def test_items(self, district_list, district, unassigned):
        assert list(district_list.items()) == [(0, unassigned), (2, district)]

    def test_index(self, district_list, district):
        assert district_list.index(district) == 1

    def test_headings(self, empty_district_list):
        assert empty_district_list.headings == ['District', 'Name', 'Population',
                                                'Deviation', '%Deviation', 'VAP',
                                                'BVAP', '%BVAP', 'APBVAP', '%APBVAP', 'WVAP', '%WVAP',
                                                'Polsby-Popper', 'Reock', 'Convex Hull']

    def test_column_keys(self, empty_district_list):
        assert empty_district_list.columnKeys == ['district', 'name', 'pop_total',
                                                  'deviation', 'pct_deviation', 'vap_total',
                                                  'vap_nh_black', 'pct_vap_nh_black',
                                                  'vap_apblack', 'pct_vap_apblack',
                                                  'vap_nh_white', 'pct_vap_nh_white',
                                                  'polsbyPopper', 'reock', 'convexHull']
