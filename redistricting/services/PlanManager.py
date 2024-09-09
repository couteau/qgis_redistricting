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
import sys
from typing import (
    Iterable,
    Optional,
    SupportsIndex,
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

from ..models import RdsPlan


class PlanManager(QObject):
    aboutToChangeActivePlan = pyqtSignal("PyQt_PyObject", "PyQt_PyObject")
    activePlanChanged = pyqtSignal("PyQt_PyObject")
    planAdded = pyqtSignal("PyQt_PyObject")
    planRemoved = pyqtSignal("PyQt_PyObject")
    cleared = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plans: list[RdsPlan] = []
        self._plansById: dict[UUID, RdsPlan] = {}
        self._activePlan = None

    @property
    def activePlan(self) -> RdsPlan:
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

    def __contains__(self, plan: RdsPlan):
        return plan in self._plans

    def setActivePlan(self, plan: Union[RdsPlan, str, UUID, None]):
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

        if plan is not None and not isinstance(plan, RdsPlan):
            QgsMessageLog.logMessage(
                self.tr('Invalid plan: {plan}').format(plan=repr(plan)), 'Redistricting', Qgis.Critical)
            return

        if plan is not None and not plan.isValid():
            QgsMessageLog.logMessage(
                self.tr('Cannot activate incomplete plan {plan}').format(plan=plan.name), 'Redistricting', Qgis.Critical)
            return

        if self._activePlan != plan:
            self.aboutToChangeActivePlan.emit(self._activePlan, plan)
            self._activePlan = plan
            self.activePlanChanged.emit(plan)

    def appendPlan(self, plan: RdsPlan, makeActive=True):
        assert isinstance(plan, RdsPlan)
        self._plans.append(plan)
        self._plansById[plan.id] = plan
        self.planAdded.emit(plan)
        if makeActive:
            self.setActivePlan(plan)

    def removePlan(self, plan: RdsPlan):
        assert isinstance(plan, RdsPlan)
        if plan in self._plans:
            if self._activePlan is plan:
                self.setActivePlan(None)
            self._plans.remove(plan)
            del self._plansById[plan.id]
            self.planRemoved.emit(plan)

    def clear(self):
        self.setActivePlan(None)
        self._plansById = {}
        self._plans = []
        self.cleared.emit()

    def extend(self, plans: Iterable[RdsPlan]):
        for plan in plans:
            self.appendPlan(plan, False)

    def get(self, key: UUID) -> Union[RdsPlan, None]:
        return self._plansById.get(key)

    def index(self, plan, start: SupportsIndex = 0, stop: SupportsIndex = sys.maxsize, /) -> int:
        return self._plans.index(plan, start, stop)
