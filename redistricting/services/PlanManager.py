# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - manage a list of plans

        begin                : 2024-03-20
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
        email                : stuart@cryptodira.org

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
from typing import (
    Iterable,
    Optional,
    Union
)
from uuid import UUID

from qgis.core import (
    Qgis,
    QgsMessageLog
)
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from ..models import RedistrictingPlan


class PlanManager(QObject):
    aboutToChangeActivePlan = pyqtSignal("PyQt_PyObject", "PyQt_PyObject")
    activePlanChanged = pyqtSignal("PyQt_PyObject")
    planAdded = pyqtSignal("PyQt_PyObject")
    planRemoved = pyqtSignal("PyQt_PyObject")

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plans: list[RedistrictingPlan] = []
        self._plansById: dict[UUID, RedistrictingPlan] = {}
        self._activePlan = None

    @property
    def activePlan(self) -> RedistrictingPlan:
        return self._activePlan

    def __bool__(self):
        return bool(self._plans)

    def __len__(self):
        return len(self._plans)

    def __getitem__(self, index: Union[int, UUID]):
        if isinstance(index, int):
            return self._plans[index]

        if isinstance(index, UUID):
            return self._plansById[index]

        raise TypeError()

    def __iter__(self):
        return iter(self._plans)

    def __contains__(self, plan: RedistrictingPlan):
        return plan in self._plans

    def setActivePlan(self, plan: Union[RedistrictingPlan, str, UUID, None]):
        if isinstance(plan, str):
            try:
                plan = UUID(plan)
            except ValueError:
                QgsMessageLog.logMessage(
                    self.tr('Plan id {uuid} not found').format(uuid=plan), 'Redistricting', Qgis.Warning)
                return

        if isinstance(plan, UUID):
            p = self._plansById.get(plan)
            if not p:
                QgsMessageLog.logMessage(
                    self.tr('Plan id {uuid} not found').format(uuid=str(plan)), 'Redistricting', Qgis.Warning)
                return
            plan = p

        if plan is not None and not isinstance(plan, RedistrictingPlan):
            QgsMessageLog.logMessage(
                self.tr('Invalid plan: {plan}').format(plan=repr(plan)), 'Redistricting', Qgis.Critical)
            return

        if plan is not None and not plan.isValid():
            QgsMessageLog.logMessage(
                self.tr('Cannot activate incomplete plan {plan}').format(plan=plan.name), 'Redistricting', Qgis.Critical)
            return

        if self._activePlan != plan:
            self.aboutToChangeActivePlan.emit(plan, self._activePlan)
            self._activePlan = plan
            self.activePlanChanged.emit(plan)

    def appendPlan(self, plan: RedistrictingPlan, makeActive=True):
        assert isinstance(plan, RedistrictingPlan)
        self._plans.append(plan)
        self._plansById[plan.id] = plan
        self.planAdded.emit(plan)
        if makeActive:
            self.setActivePlan(plan)

    def removePlan(self, plan: RedistrictingPlan):
        assert isinstance(plan, RedistrictingPlan)
        if plan in self._plans:
            if self._activePlan is plan:
                self.setActivePlan(None)
            self._plans.remove(plan)
            del self._plansById[plan.id]
            self.planRemoved.emit(plan)

    def clear(self):
        self.setActivePlan(None)
        self._plans = []
        self._plansById = {}

    def extend(self, plans: Iterable[RedistrictingPlan]):
        for plan in plans:
            self.appendPlan(plan, False)

    def get(self, key: UUID) -> Union[RedistrictingPlan, None]:
        return self._plansById.get(key)