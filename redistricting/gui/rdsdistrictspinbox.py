"""QGIS Redistricting Plugins - A QSpinBox that will skip/refuse district
        numbers that are already in use

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

from typing import Optional, Tuple

from qgis.PyQt.QtGui import QIntValidator, QValidator
from qgis.PyQt.QtWidgets import QSpinBox, QWidget

from ..models import RdsPlan


class RdsDistrictSpinBox(QSpinBox):
    def __init__(self, parent: Optional[QWidget] = ...):
        super().__init__(parent)
        self._plan: RdsPlan = None

    def plan(self) -> RdsPlan:
        return self._plan

    def setPlan(self, plan: RdsPlan):
        self._plan = plan

    def _findNextValidValue(self, value, steps):
        if not self._plan or steps not in (-1, 1):
            return value

        v = value + steps
        while 0 < v <= self._plan.numDistricts and v in self._plan.districts.keys():
            v += steps

        if 0 < v <= self._plan.numDistricts:
            return v

        return None

    def stepBy(self, steps: int):
        v = self._findNextValidValue(self.value(), steps)
        if v is not None:
            self.setValue(v)
        else:
            super().stepBy(steps)

    def validate(self, inp: str, pos: int) -> Tuple[QValidator.State, str, int]:
        if not self._plan:
            return super().validate(inp, pos)

        validator = QIntValidator(self.minimum(), self.maximum(), self)
        valid, inp, pos = validator.validate(inp, pos)
        if valid != QValidator.Invalid:
            if inp.isnumeric():
                v = int(inp)
                if v in self._plan.districts.keys():
                    valid = QValidator.Intermediate

        return (valid, inp, pos)

    def fixup(self, inp: str) -> str:
        v = super().fixup(inp)
        if v.isnumeric():
            result = self._findNextValidValue(int(v), 1)
            if result is None:
                result = self._findNextValidValue(int(v), -1)

            if result is not None:
                return str(result)

        return v
