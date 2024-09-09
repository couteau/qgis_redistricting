"""QGIS Redistricting Plugin - unit tests for RdsFieldTableView class"""
import pytest
from pytestqt.plugin import QtBot
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon

from redistricting.gui.RdsFieldTableView import (
    FieldListModel,
    RdsFieldTableView
)
from redistricting.models import (
    RdsDataField,
    RdsField
)


class TestFieldTableView:
    @pytest.fixture
    def field_list(self, block_layer) -> list[RdsField]:
        f = RdsField(block_layer, 'vtdid')
        return [f]

    @pytest.fixture
    def field_list_two(self, block_layer) -> list[RdsField]:
        return [RdsField(block_layer, 'vtdid'), RdsField(block_layer, 'countyid')]

    @pytest.fixture
    def data_field_list(self, block_layer) -> list[RdsDataField]:
        f = RdsDataField(block_layer, 'vap_nh_white')
        return [f]

    @pytest.fixture
    def field_list_model(self, field_list) -> FieldListModel:
        return FieldListModel(field_list)

    @pytest.fixture
    def field_list_model_two(self, field_list_two) -> FieldListModel:
        return FieldListModel(field_list_two)

    @pytest.fixture
    def datafield_list_model(self, data_field_list) -> FieldListModel:
        return FieldListModel(data_field_list)

    @pytest.fixture
    def field_table_view(self, field_list_model_two):
        v = RdsFieldTableView()
        v.setModel(field_list_model_two)
        v.setEnableDragRows(True)
        return v

    def test_field_model(self, field_list, data_field_list, qtmodeltester):
        model = FieldListModel(fields=field_list)
        qtmodeltester.check(model)
        model = FieldListModel(fields=data_field_list)
        qtmodeltester.check(model)

    def test_add_field(self, block_layer, field_list_model: FieldListModel, qtbot: QtBot):
        with qtbot.waitSignals([field_list_model.rowsAboutToBeInserted, field_list_model.rowsInserted]):
            field_list_model.appendField(block_layer, 'countyid')
        assert field_list_model.rowCount() == 2

    def test_move_field(self, field_list_model_two: FieldListModel, qtbot: QtBot):
        with qtbot.waitSignals([field_list_model_two.rowsAboutToBeMoved, field_list_model_two.rowsMoved]):
            field_list_model_two.moveField(1, 0)
        assert field_list_model_two.fields[0].field == 'countyid'

    def test_delete_field(self, field_list_model_two: FieldListModel, qtbot: QtBot):
        with qtbot.waitSignals([field_list_model_two.rowsAboutToBeRemoved, field_list_model_two.rowsRemoved]):
            field_list_model_two.deleteField(0)
        assert field_list_model_two.rowCount() == 1
        assert field_list_model_two.fields[0].field == 'countyid'

    def test_disallow_add_duplicate(self, block_layer, field_list_model: FieldListModel):
        field_list_model.appendField(block_layer, 'vtdid')
        assert field_list_model.rowCount() == 1

    def test_data(self, datafield_list_model: FieldListModel):
        data = datafield_list_model.data(datafield_list_model.createIndex(0, 0), Qt.DisplayRole)
        assert data == 'vap_nh_white'
        data = datafield_list_model.data(datafield_list_model.createIndex(0, 0), Qt.DecorationRole)
        assert isinstance(data, QIcon)
        data = datafield_list_model.data(datafield_list_model.createIndex(0, 2), Qt.CheckStateRole)
        assert data == Qt.Checked

    def test_set_data(self, datafield_list_model: FieldListModel):
        assert not datafield_list_model.setData(datafield_list_model.createIndex(0, 0), 'dummy', Qt.EditRole)
        assert datafield_list_model.setData(datafield_list_model.createIndex(0, 1), 'WVAP', Qt.EditRole)
        assert datafield_list_model.fields[0].caption == 'WVAP'

    def test_flags(self, datafield_list_model: FieldListModel):
        assert datafield_list_model.flags(datafield_list_model.createIndex(0, 1)) & Qt.ItemIsEditable
        assert datafield_list_model.flags(datafield_list_model.createIndex(0, 2)) & Qt.ItemIsUserCheckable
