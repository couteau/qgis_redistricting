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
    def district_list(self, plan) -> DistrictList:
        dist = DistrictList(plan)
        dist.addDistrict(2, 'District 2')
        return dist

    @pytest.fixture
    def district(self, district_list: DistrictList) -> District:
        return district_list['2']

    @pytest.fixture
    def unassigned(self, district_list) -> Unassigned:
        return district_list['0']

    def test_create(self, empty_district_list):
        assert len(empty_district_list) == 1
        assert empty_district_list[0].name == 'Unassigned'

    def test_add_district(self, empty_district_list):
        empty_district_list.addDistrict(2, 'District 2')
        assert len(empty_district_list) == 2
        assert empty_district_list[1].name == 'District 2'

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

    def test_getitem(self, district_list, district):
        assert district_list['2'] == district
        assert district_list[1] == district
        with pytest.raises(IndexError):
            district_list[2]  # pylint: disable=pointless-statement

        assert district_list['1'] is None
        with pytest.raises(IndexError):
            district_list['7']  # pylint: disable=pointless-statement

        l = district_list[1:]
        assert isinstance(l, DistrictList)
        assert len(l) == 1
        assert l[0] == district
