from typing import (
    Callable,
    Optional,
    Union
)

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import (
    QIcon,
    QKeySequence
)
from qgis.PyQt.QtWidgets import QAction


class ActionRegistry:
    _instance = None
    _actions: dict[str, QAction]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ActionRegistry, cls).__new__(cls)
            cls._instance._actions = {}

        return cls._instance

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
        if isinstance(icon, str):
            icon = QIcon(icon)

        action = QAction(icon, text, parent)
        if tooltip is not None:
            action.setToolTip(tooltip)
        if shortcut is not None:
            action.setShortcut(shortcut)

        action.setCheckable(checkable)

        if callback is not None:
            action.triggered.connect(callback)

        self.registerAction(name, action)

        return action

    def registerAction(self, name: str, action: QAction):
        self._actions[name] = action

    def findAction(self, name: str):
        return self._actions.get(name)

    def __getattr__(self, attr):
        if attr not in self._actions:
            raise AttributeError()

        return self._actions[attr]
