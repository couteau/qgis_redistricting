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
from math import (
    ceil,
    floor
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import (
        RdsDistrict,
        RdsPlan
    )


class DistrictValidator:
    """Validate whether district population is within allowable deviation for plan
    """

    def validateDistrict(self, plan: "RdsPlan", district: "RdsDistrict"):
        maxDeviation = district.members * int(plan.totalPopulation * plan.deviation / plan.numDistricts)
        idealUpper = ceil(district.members * plan.totalPopulation / plan.numSeats) + maxDeviation
        idealLower = floor(district.members * plan.totalPopulation / plan.numSeats) - maxDeviation
        return idealLower <= district.population <= idealUpper
