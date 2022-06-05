"""QGIS Redistricting Plugin - unit tests for RdsFieldTableView class"""
import pytest

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush
from redistricting.core import DistrictDataModel

# pylint: disable=no-self-use


class TestPlanDataModelView:
    @pytest.fixture
    def district_model(self, plan) -> DistrictDataModel:
        return DistrictDataModel(plan)

    def test_model(self, district_model, qtmodeltester):
        qtmodeltester.check(district_model)

    def test_rowcount(self, district_model):
        assert district_model.rowCount() == 3

    def test_colcount(self, district_model):
        assert district_model.columnCount() == 15

    def test_headerdata(self, district_model):
        data = district_model.headerData(14, Qt.Horizontal, Qt.DisplayRole)
        assert data == 'Convex Hull'

    def test_data(self, district_model: DistrictDataModel):
        data = district_model.data(district_model.createIndex(0, 1), Qt.DisplayRole)
        assert data == 'Unassigned'
        data = district_model.data(district_model.createIndex(0, 0), Qt.BackgroundRole)
        assert isinstance(data, QBrush)

    # pylint: disable=protected-access
    def test_headings(self, district_model: DistrictDataModel):
        assert district_model._headings == ['District', 'Name', 'Population',
                                            'Deviation', '%Deviation', 'VAP',
                                            'BVAP', '%BVAP', 'APBVAP', '%APBVAP', 'WVAP', '%WVAP',
                                            'Polsby-Popper', 'Reock', 'Convex Hull']

    def test_column_keys(self, district_model: DistrictDataModel):
        assert district_model._keys == ['district', 'name', 'pop_total',
                                        'deviation', 'pct_deviation', 'vap_total',
                                        'vap_nh_black', 'pct_vap_nh_black',
                                        'vap_apblack', 'pct_vap_apblack',
                                        'vap_nh_white', 'pct_vap_nh_white',
                                        'polsbyPopper', 'reock', 'convexHull']
    # pylint: enable=protected-access
