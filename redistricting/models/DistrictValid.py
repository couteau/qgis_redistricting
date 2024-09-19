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
    from . import (
        RdsDistrict,
        RdsPlan
    )


class BaseDeviationValidator(QObject):
    def __init__(self, plan: 'RdsPlan', parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = plan
        self.updateIdeal()

    def updateIdeal(self):
        self._perMemberIdeal = self._plan.totalPopulation / self._plan.numSeats

    def districtIdeal(self, district: 'RdsDistrict'):
        return district.members * self._perMemberIdeal

    def districtPctDeviation(self, district: 'RdsDistrict'):
        return (district.population - (district.members * self._perMemberIdeal)) / (district.members * self._perMemberIdeal)

    def totalDeviation(self):
        deviations = [self.districtPctDeviation(d) for d in self._plan.districts if d.district != 0]
        return max(*deviations) - min(deviations)

    def minmaxDeviations(self):
        deviations = [self.districtPctDeviation(d) for d in self._plan.districts if d.district != 0]
        return min(deviations), max(*deviations)

    @abstractmethod
    def validateDistrict(self, district: 'RdsDistrict'):
        """Validate whether district population is within allowable deviation"""


class PlusMinusDeviationValidator(BaseDeviationValidator):
    """Validate whether district population is between +/-allowable deviation
    """

    def validateDistrict(self, district: 'RdsDistrict'):
        maxDeviation = district.members * int(self._plan.deviation * self._perMemberIdeal)
        idealUpper = ceil(district.members * self._perMemberIdeal) + maxDeviation
        idealLower = floor(district.members * self._perMemberIdeal) - maxDeviation
        return idealLower <= district.population <= idealUpper


class MaxDeviationValidator(BaseDeviationValidator):
    """Validate whether district population keeps total plan deviation within allowable range
    """

    def validateDistrict(self, district: 'RdsDistrict'):
        pctDeviation = self.districtPctDeviation(district)
        districtDeviations = [
            self.districtPctDeviation(d) for d in self._plan.districts if d is not district and d.district != 0
        ]
        planMax = max(*districtDeviations)
        planMin = min(*districtDeviations)

        return planMin <= pctDeviation <= planMin + self._plan.deviation or planMax - self._plan.deviation <= pctDeviation <= planMax
