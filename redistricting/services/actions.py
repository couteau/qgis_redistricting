# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - action registry

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
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
    TYPE_CHECKING,
    Callable,
    Optional,
    Union
)

from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)
from qgis.PyQt.QtGui import (
    QIcon,
    QKeySequence
)
from qgis.PyQt.QtWidgets import QAction

if TYPE_CHECKING:
    from ..models import RedistrictingPlan


class PlanAction(QAction):
    triggeredForPlan = pyqtSignal('PyQt_PyObject')

    def __init__(self, p1=..., p2=..., p3=...):
        if p3 is ...:
            if p2 is ...:
                if p1 is ...:
                    super().__init__()
                else:
                    super().__init__(p1)
            else:
                super().__init__(p1, p2)
        else:
            super().__init__(p1, p2, p3)

        self._plan = None

    def setTarget(self, plan: "RedistrictingPlan"):
        self._plan = plan

    def triggerForPlan(self, plan: "RedistrictingPlan"):
        self.setTarget(plan)
        self.triggeredForPlan.emit(plan)

    def trigger(self):
        self.triggeredForPlan.emit(self._plan)
        super().trigger()


class ActionRegistry:
    _instance = None
    _actions: dict[str, QAction]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ActionRegistry, cls).__new__(cls)
            cls._instance._actions = {}

        return cls._instance

    def _createAction(
        self,
        name: str,
        icon: Union[str, QIcon],
        text: str,
        tooltip: Optional[str] = None,
        shortcut: Optional[Union[QKeySequence, QKeySequence.StandardKey, str, int]] = None,
        checkable: bool = False,
        parent: Optional[QObject] = None,
        actionCls=QAction
    ) -> QAction:
        if isinstance(icon, str):
            icon = QIcon(icon)

        action = actionCls(icon, text, parent)
        if tooltip is not None:
            action.setToolTip(tooltip)
        if shortcut is not None:
            action.setShortcut(shortcut)

        action.setCheckable(checkable)

        self.registerAction(name, action)

        return action

    def createAction(
        self,
        name: str,
        icon: Union[str, QIcon],
        text: str,
        tooltip: Optional[str] = None,
        shortcut: Optional[Union[QKeySequence, QKeySequence.StandardKey, str, int]] = None,
        checkable: bool = False,
        callback: Optional[Callable[[], None]] = None,
        parent: Optional[QObject] = None
    ) -> QAction:
        action = self._createAction(name, icon, text, tooltip, shortcut, checkable, parent)
        if callback is not None:
            action.triggered.connect(callback)
        return action

    def createPlanAction(
        self,
        name: str,
        icon: Union[str, QIcon],
        text: str,
        tooltip: Optional[str] = None,
        shortcut: Optional[Union[QKeySequence, QKeySequence.StandardKey, str, int]] = None,
        checkable: bool = False,
        callback: Optional[Callable[[], None]] = None,
        parent: Optional[QObject] = None
    ) -> QAction:
        action: PlanAction = self._createAction(
            name, icon, text, tooltip, shortcut, checkable, parent, actionCls=PlanAction
        )
        if callback is not None:
            action.triggeredForPlan.connect(callback)
        return action

    def registerAction(self, name: str, action: QAction):
        self._actions[name] = action

    def findAction(self, name: str):
        return self._actions.get(name)

    def __getattr__(self, attr) -> Union[QAction, PlanAction]:
        if attr not in self._actions:
            raise AttributeError()

        return self._actions[attr]
