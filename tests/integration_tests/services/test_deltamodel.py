"""QGIS Redistricting Plugin - integration tests

Copyright 2022-2024, Stuart C. Naifeh

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
import pandas as pd
import pytest
from qgis.PyQt.QtCore import Qt

from redistricting.models import (
    DeltaList,
    RdsPlan
)
from redistricting.services import (
    DeltaListModel,
    PlanEditor
)

# pylint: disable=unused-argument,protected-access


class TestDeltaModel:
    @pytest.fixture
    def delta_model(self, plan):
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
            },
                {
                'district': 2,
                'pop_total': -7,
                'new_pop_total': 80,
                'deviation': -5,
                'pct_deviation': -0.20,
                'vap_total': -5,
                'new_vap_total': 50,
                'vap_apblack': -5,
                'new_vap_apblack': 25,
                'pct_vap_apblack': 0.5,
                'vap_nh_white': -3,
                'new_vap_nh_white': 20,
                'pct_vap_nh_white': 0.4,
                'vap_hispanic': 0,
                'new_vap_hispanic': 5,
                'pct_vap_hispanic': 0.1
            },
                {
                'district': 3,
                'pop_total': -7,
                'new_pop_total': 80,
                'deviation': -5,
                'pct_deviation': -0.20,
                'vap_total': -5,
                'new_vap_total': 50,
                'vap_apblack': -5,
                'new_vap_apblack': 25,
                'pct_vap_apblack': 0.5,
                'vap_nh_white': -3,
                'new_vap_nh_white': 20,
                'pct_vap_nh_white': 0.4,
                'vap_hispanic': 0,
                'new_vap_hispanic': 5,
                'pct_vap_hispanic': 0.1
            }],
            index='district'
        )
        delta = DeltaList()
        delta.setData(df)
        model = DeltaListModel()
        model.setPlan(plan, delta)
        model._delta._data = df
        return model

    def test_model(self, delta_model: DeltaListModel, qtmodeltester):
        qtmodeltester.check(delta_model)
        assert delta_model.rowCount() == 3
        assert delta_model.columnCount() == 15
        assert delta_model.data(delta_model.createIndex(2, 0), Qt.DisplayRole) == '-7'

    def test_update_fields(self, delta_model: DeltaListModel, plan: RdsPlan, block_layer):
        assert delta_model.columnCount() == 15
        e = PlanEditor.fromPlan(plan)
        e.appendDataField('vap_nh_black')
        e.updatePlan()
        assert delta_model.columnCount() == 18
