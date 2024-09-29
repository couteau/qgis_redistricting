"""QGIS Redistricting Plugin - unit tests for DeltaList class"""
import pandas as pd
import pytest
from pytest_mock import MockerFixture
from qgis.PyQt.QtCore import (
    Qt,
    pyqtBoundSignal
)

from redistricting.models import DeltaList
from redistricting.services import DeltaListModel

# pylint: disable=unused-argument,protected-access


class TestDeltaModel:
    @pytest.fixture
    def empty_model(self, plan):
        model = DeltaListModel()
        model.setDelta(plan, None)
        return model

    @pytest.fixture
    def mock_delta(self, mocker: MockerFixture):
        df = pd.DataFrame.from_records(
            [{
                'district': 1,
                'pop_total': 7,
                'new_pop_total': 95,
                'deviation': 5,
                'pct_deviation': 0.05,
                'vap_total': 5,
                'new_vap_total': 80,
                'vap_apblack': -5,
                'new_vap_apblack': 25,
                'pct_vap_apblack': 0.3125,
                'vap_nh_white': 3,
                'new_vap_nh_white': 40,
                'pct_vap_nh_white': 0.5,
                'vap_hispanic': 0,
                'new_vap_hispanic': 10,
                'pct_vap_hispanic': 0.125
            }],
            index='district'
        )
        delta = mocker.create_autospec(spec=DeltaList)
        delta.__bool__.return_value = True
        delta._data = df
        type(delta).updateStarted = mocker.create_autospec(spec=pyqtBoundSignal)
        type(delta).updateComplete = mocker.create_autospec(spec=pyqtBoundSignal)
        return delta

    @pytest.fixture
    def delta_model(self, plan, mock_delta):
        model = DeltaListModel()
        model.setDelta(plan, mock_delta)

        yield model

    def test_create(self, empty_model: DeltaListModel):
        assert empty_model.columnCount() == 15

    def test_model(self, delta_model, empty_model, qtmodeltester):
        qtmodeltester.check(delta_model)
        qtmodeltester.check(empty_model)

    def test_heading(self, delta_model: DeltaListModel):
        assert delta_model.headerData(3, Qt.Horizontal, Qt.DisplayRole) == '%Deviation'

    def test_update_districts(self, delta_model, mock_delta):
        mock_delta.__len__.return_value = 1
        assert delta_model.rowCount() == 1
