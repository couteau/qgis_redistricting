"""QGIS Redistricting Plugin - unit tests for DistrictList class"""
import pytest
import geopandas as gpd
from redistricting.core.DistrictList import DistrictList
from redistricting.core.District import District, Unassigned


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
    def dataframe(self, datadir):
        df: gpd.GeoDataFrame = gpd.read_file(
            str((datadir / 'test.json').resolve()),
            index='district',
            geometry='geometry'
        )
        df.set_index('district', inplace=True)
        return df

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

    def test_del_district(self, district_list, district):
        del district_list[district]
        assert len(district_list) == 1

    def test_del_str_index(self, district_list):
        del district_list['2']
        assert len(district_list) == 1

    def test_del_int_index(self, district_list):
        del district_list[2]
        assert len(district_list) == 1

    def test_del_bad_index_throws_exception(self, district_list):
        with pytest.raises(IndexError):
            del district_list[4]

        with pytest.raises(IndexError):
            del district_list['abc']

    def test_del_bad_index_type_throws_exception(self, district_list):
        with pytest.raises(IndexError):
            del district_list[None]

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

        l = district_list['reock']
        assert isinstance(l, list)
        assert len(l) == 1

    def test_loaddata(self, empty_district_list):
        empty_district_list.loadData(True)
        assert len(empty_district_list) == 6

    def test_update_data_new_districts(self, empty_district_list, dataframe):
        empty_district_list.updateData(dataframe)
        assert len(empty_district_list) == 6
        assert empty_district_list[1].population == 44684

    def test_update_data_existing_districts(self, district_list, dataframe):
        assert district_list['2'].population == 0
        district_list.updateData(dataframe)
        assert len(district_list) == 6
        assert district_list[2].population == 46916
