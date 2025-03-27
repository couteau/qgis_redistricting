"""QGIS Redistricting Plugin - district validator

        begin                : 2024-03-18
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
from abc import abstractmethod
from enum import IntEnum
from math import (
    ceil,
    floor
)
from typing import (
    TYPE_CHECKING,
    Optional
)

from qgis.PyQt.QtCore import QObject

if TYPE_CHECKING:
    from .district import RdsDistrict
    from .plan import RdsPlan


class DeviationType(IntEnum):
    OverUnder = 0
    TopToBottom = 1


class BaseDeviationValidator(QObject):
    def __init__(self, plan: 'RdsPlan', parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = plan
        self.updateIdeal()

    def updateIdeal(self):
        self._perMemberIdeal = self._plan.totalPopulation / self._plan.numSeats

    def districtIdeal(self, district: 'RdsDistrict') -> float:
        return district.members * self._perMemberIdeal

    def districtIdealRange(self, district: 'RdsDistrict') -> tuple[float, int, int]:
        ideal = self.districtIdeal(district)
        return ideal, floor(ideal), ceil(ideal)

    def districtPctDeviation(self, district: 'RdsDistrict') -> float:
        if self._perMemberIdeal == 0:
            return 0

        return (district.population - (district.members * self._perMemberIdeal)) / (district.members * self._perMemberIdeal)

    def totalDeviation(self) -> float:
        deviations = [self.districtPctDeviation(d) for d in self._plan.districts if d.district != 0]
        return max(*deviations) - min(*deviations)

    def minmaxDeviations(self):
        deviations = [self.districtPctDeviation(d) for d in self._plan.districts if d.district != 0]
        if len(deviations) == 0:
            return None, None

        return min(deviations, default=0), max(deviations, default=0)

    @abstractmethod
    def validateDistrict(self, district: 'RdsDistrict') -> bool:
        """Validate whether district population is within allowable deviation"""

    def validatePlan(self) -> bool:
        return all(self.validateDistrict(d) for d in self._plan.districts[1:])


class PlusMinusDeviationValidator(BaseDeviationValidator):
    """Validate whether district population is between +/-allowable deviation
    """

    def validateDistrict(self, district: 'RdsDistrict'):
        ideal, idealLower, idealUpper = self. districtIdealRange(district)
        maxDev = self._plan.deviation * ideal

        return min(idealLower, ideal - maxDev) <= district.population <= max(idealUpper, ideal + maxDev)


class MaxDeviationValidator(BaseDeviationValidator):
    """Validate whether district population keeps total plan deviation within allowable range
    """

    def validateDistrict(self, district: 'RdsDistrict'):
        districtIdeal, districtIdealMin, districtIdealMax = self.districtIdealRange((district))
        if districtIdealMin <= district.population <= districtIdealMax:
            return True

        minPctIdeal = (districtIdealMin - districtIdeal) / districtIdeal
        maxPctIdeal = (districtIdealMax - districtIdeal) / districtIdeal
        maxPctOver = max(maxPctIdeal, self._plan.deviation * (self._plan.numSeats - 1) / self._plan.numSeats)
        maxPctUnder = min(minPctIdeal, -self._plan.deviation * (self._plan.numSeats - 1) / self._plan.numSeats)
        pctDeviation = self.districtPctDeviation(district)

        if pctDeviation < maxPctUnder or pctDeviation > maxPctOver:
            return False

        deviations = []
        for d in self._plan.districts:
            dev = self.districtPctDeviation(d)
            if d is not district and d.district != 0 and maxPctUnder <= dev <= maxPctOver:
                deviations.append(dev)

        planMax = max(deviations, default=maxPctOver)
        planMin = min(deviations, default=maxPctUnder)
        return planMin <= pctDeviation <= max(planMin + self._plan.deviation, maxPctIdeal) \
            or min(planMax - self._plan.deviation, minPctIdeal) <= pctDeviation <= planMax

    def validatePlan(self) -> bool:
        return self.totalDeviation() <= self._plan.deviation


validators: dict[DeviationType, type[BaseDeviationValidator]] = {
    DeviationType.OverUnder: PlusMinusDeviationValidator,
    DeviationType.TopToBottom: MaxDeviationValidator
}
