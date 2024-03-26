"""QGIS Redistricting Plugin - unit tests for RedistrictingPlan class

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
import sqlite3

import pytest
from pytest_mock import MockerFixture
from pytestqt.plugin import QtBot
from qgis.core import (
    Qgis,
    QgsProject
)

from redistricting.models import RedistrictingPlan
from redistricting.services import PlanCopier

# pylint: disable=protected-access


class TestPlanCopier:
    @pytest.fixture
    def copier(self, valid_plan: RedistrictingPlan):
        return PlanCopier(valid_plan)

    def test_create(self, valid_plan: RedistrictingPlan):
        copier = PlanCopier(valid_plan)
        assert copier._plan is valid_plan

    def test_copy_without_assignments(self, copier: PlanCopier, datadir, mocker: MockerFixture):
        builder_class = mocker.patch('redistricting.core.PlanCopy.PlanBuilder')
        builder = builder_class.fromPlan.return_value
        copier.copyPlan('copied', 'copy of plan', str(datadir / 'copied.gpkg'), False, False)
        builder_class.fromPlan.assert_called_once()
        builder.setName.assert_called_once()
        builder.createPlan.assert_called_once_with(QgsProject.instance(), True)

    def test_copy_with_assignments(self, copier: PlanCopier, datadir, mocker: MockerFixture, qtbot: QtBot):
        builder_class = mocker.patch('redistricting.core.PlanCopy.PlanBuilder')
        builder = builder_class.fromPlan.return_value
        with qtbot.wait_signal(copier.copyComplete):
            copier.copyPlan('copied', 'copy of plan', str(datadir / 'copied.gpkg'), True, False)
        builder_class.fromPlan.assert_called_once()
        builder.setName.assert_called_once()
        builder.createPlan.assert_called_once_with(QgsProject.instance(), False)

    def test_copy_with_styles(self, copier: PlanCopier, datadir, mocker: MockerFixture):
        builder_class = mocker.patch('redistricting.core.PlanCopy.PlanBuilder')
        builder = builder_class.fromPlan.return_value
        styler_class = mocker.patch('redistricting.core.PlanCopy.PlanStyler')
        styler = styler_class.return_value

        plan = copier.copyPlan('copied', 'copy of plan', str(datadir / 'copied.gpkg'), True, True)
        builder_class.fromPlan.assert_called_once()
        builder.setName.assert_called_once()
        builder.createPlan.assert_called_once_with(QgsProject.instance(), False)

        styler_class.assert_called_once_with(plan)
        styler.copyStyles.assert_called_once()

    def test_copy_no_gpkg_raises_error(self, copier: PlanCopier, mocker: MockerFixture):
        mocker.patch('redistricting.core.PlanCopy.PlanBuilder')
        with pytest.raises(ValueError):
            plan = copier.copyPlan('copied', 'copy of plan',  None)
            assert not plan

    def test_copy_create_errors_sets_error(self, copier: PlanCopier, datadir, mocker: MockerFixture):
        builder_class = mocker.patch('redistricting.core.PlanCopy.PlanBuilder')
        builder = builder_class.fromPlan.return_value
        builder.createPlan.return_value = None
        builder.errors.return_value = [('create error', Qgis.Critical)]
        plan = copier.copyPlan('copied', 'copy of plan', str(datadir / 'copied.gpkg'), False, False)
        assert not plan
        assert copier.errors() == [('create error', Qgis.Critical)]

    def test_copy_assignments(self, copier: PlanCopier, new_plan: RedistrictingPlan):
        with sqlite3.connect(new_plan.geoPackagePath) as db:
            c = db.execute('SELECT count(distinct district) FROM assignments')
            assert c.fetchone()[0] == 1
        copier.copyAssignments(new_plan)
        with sqlite3.connect(new_plan.geoPackagePath) as db:
            c = db.execute('SELECT count(distinct district) FROM assignments')
            assert c.fetchone()[0] == 5
