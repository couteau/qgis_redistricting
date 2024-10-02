"""QGIS Redistricting Plugin - unit tests

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
from pytest_mock import MockerFixture

from redistricting.models import (
    RdsDistrict,
    RdsPlan
)
from redistricting.models.District import RdsUnassigned
from redistricting.models.DistrictValid import (
    MaxDeviationValidator,
    PlusMinusDeviationValidator
)


class TestDistrictValidator:
    def test_overunder_validate_district(self, mocker: MockerFixture):
        plan = mocker.create_autospec(spec=RdsPlan)
        plan.totalPopulation = 500
        plan.numDistricts = 5
        plan.numSeats = 5
        plan.deviation = 0.05

        districts = []
        district = mocker.create_autospec(spec=RdsUnassigned)
        district.district = 0
        districts.append(district)

        for d in range(1, 6):
            district = mocker.create_autospec(spec=RdsDistrict)
            district.district = d
            district.members = 1
            districts.append(district)

        v = PlusMinusDeviationValidator(plan)
        type(plan).districts = mocker.PropertyMock(return_value=districts)

        district = mocker.create_autospec(spec=RdsDistrict)
        district.members = 1

        districts[1].population = 100
        districts[2].population = 100
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 105
        districts[2].population = 95
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 106
        districts[2].population = 95
        districts[3].population = 99
        districts[4].population = 100
        districts[5].population = 100
        assert not v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 105
        districts[2].population = 94
        districts[3].population = 101
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert not v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.population = 501
        v.updateIdeal()
        districts[1].population = 106
        districts[2].population = 95
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert not v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 105
        districts[2].population = 94
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert not v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.totalPopulation = 499
        v.updateIdeal()
        districts[1].population = 105
        districts[2].population = 95
        districts[3].population = 99
        districts[4].population = 100
        districts[5].population = 100
        assert not v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 104
        districts[2].population = 94
        districts[3].population = 101
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert not v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.deviation = 0
        plan.population = 500
        v.updateIdeal()
        districts[1].population = 100
        districts[2].population = 100
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.totalPopulation = 501
        v.updateIdeal()
        districts[1].population = 101
        districts[2].population = 100
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.totalPopulation = 504
        v.updateIdeal()
        districts[1].population = 101
        districts[2].population = 101
        districts[3].population = 101
        districts[4].population = 101
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.totalPopulation = 499
        v.updateIdeal()
        districts[1].population = 99
        districts[2].population = 100
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.totalPopulation = 496
        v.updateIdeal()
        districts[1].population = 99
        districts[2].population = 99
        districts[3].population = 99
        districts[4].population = 99
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

    def test_overunder_validate_district_multi_member(self, mocker: MockerFixture):
        plan = mocker.create_autospec(spec=RdsPlan)
        plan.totalPopulation = 1000
        plan.numDistricts = 5
        plan.numSeats = 10
        plan.deviation = 0.05
        v = PlusMinusDeviationValidator(plan)

        district = mocker.create_autospec(spec=RdsDistrict)
        district.members = 2

        district.population = 200
        assert v.validateDistrict(district)

        district.population = 210
        assert v.validateDistrict(district)

        district.population = 190
        assert v.validateDistrict(district)

        district.population = 211
        assert not v.validateDistrict(district)

        district.population = 189
        assert not v.validateDistrict(district)

        plan.deviation = 0
        district.population = 200
        assert v.validateDistrict(district)

    def test_totaldeviation_validate_district(self, mocker: MockerFixture):
        plan = mocker.create_autospec(spec=RdsPlan)
        plan.totalPopulation = 500
        plan.numDistricts = 5
        plan.numSeats = 5
        plan.deviation = 0.10

        districts = []
        district = mocker.create_autospec(spec=RdsUnassigned)
        district.district = 0
        districts.append(district)

        for d in range(1, 6):
            district = mocker.create_autospec(spec=RdsDistrict)
            district.district = d
            district.members = 1
            districts.append(district)

        type(plan).districts = mocker.PropertyMock(return_value=districts)
        v = MaxDeviationValidator(plan)

        districts[1].population = 107
        districts[2].population = 98
        districts[3].population = 99
        districts[4].population = 99
        districts[5].population = 97
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 102
        districts[2].population = 102
        districts[3].population = 102
        districts[4].population = 102
        districts[5].population = 92

        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 103
        districts[2].population = 101
        assert not v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert not v.validateDistrict(districts[5])

        plan.deviation = 0
        districts[1].population = 100
        districts[2].population = 100
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 101
        districts[2].population = 99
        assert not v.validateDistrict(districts[1])
        assert not v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.totalPopulation = 502
        v.updateIdeal()
        districts[1].population = 101
        districts[2].population = 101
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 102
        districts[2].population = 100
        assert not v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.totalPopulation = 499
        v.updateIdeal()
        districts[1].population = 99
        districts[2].population = 100
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.totalPopulation = 498
        v.updateIdeal()
        districts[1].population = 99
        districts[2].population = 99
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 98
        districts[2].population = 100
        assert not v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.deviation = 0.0021
        plan.totalPopulation = 499
        v.updateIdeal()
        districts[1].population = 99
        districts[2].population = 100
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.deviation = .10
        plan.totalPopulation = 500
        v.updateIdeal()
        districts[1].population = 108
        districts[2].population = 108
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 50
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert not v.validateDistrict(districts[5])

    def test_totaldeviation_validate_district_incomplete_plan(self, mocker: MockerFixture):
        plan = mocker.create_autospec(spec=RdsPlan)
        plan.totalPopulation = 500
        plan.numDistricts = 5
        plan.allocatedDistricts = 3
        plan.numSeats = 5
        plan.allocatedSeats = 3
        plan.deviation = 0.10

        districts = []
        district = mocker.create_autospec(spec=RdsUnassigned)
        district.district = 0
        districts.append(district)

        for d in range(1, 4):
            district = mocker.create_autospec(spec=RdsDistrict)
            district.district = d
            district.members = 1
            districts.append(district)

        type(plan).districts = mocker.PropertyMock(return_value=districts)
        v = MaxDeviationValidator(plan)

        districts[1].population = 107
        districts[2].population = 99
        districts[3].population = 97
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])

        districts[1].population = 108
        districts[2].population = 99
        districts[3].population = 97
        assert not v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert not v.validateDistrict(districts[3])

        districts[1].population = 108
        districts[2].population = 98
        districts[3].population = 98
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])

        districts[1].population = 108
        districts[2].population = 99
        districts[3].population = 98
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])

        districts[1].population = 109
        districts[2].population = 99
        districts[3].population = 98
        assert not v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])

        districts[1].population = 102
        districts[2].population = 102
        districts[3].population = 92
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])

        districts[1].population = 108
        districts[2].population = 108
        districts[3].population = 50
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert not v.validateDistrict(districts[3])

    def test_totaldeviation_validate_district_multimember(self, mocker: MockerFixture):
        plan = mocker.create_autospec(spec=RdsPlan)
        plan.totalPopulation = 500
        plan.numDistricts = 5
        plan.allocatedDistricts = 5
        plan.numSeats = 10
        plan.allocatedSeats = 10
        plan.deviation = 0.10

        districts = []
        district = mocker.create_autospec(spec=RdsUnassigned)
        district.district = 0
        districts.append(district)

        for d in range(1, 6):
            district = mocker.create_autospec(spec=RdsDistrict)
            district.district = d
            district.members = 2
            districts.append(district)

        type(plan).districts = mocker.PropertyMock(return_value=districts)
        v = MaxDeviationValidator(plan)

        districts[1].population = 100
        districts[2].population = 100
        districts[3].population = 100
        districts[4].population = 100
        districts[5].population = 100
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].members = 4
        districts[1].population = 200
        districts[2].population = 100
        districts[3].population = 100
        districts[4].members = 1
        districts[4].population = 50
        districts[5].members = 1
        districts[5].population = 50
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.deviation = 0
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        plan.totalPopulation = 501
        v.updateIdeal()
        districts[1].population = 201
        districts[2].population = 100
        districts[3].population = 100
        districts[4].population = 50
        districts[5].population = 50
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])

        districts[1].population = 200
        districts[2].population = 101
        districts[3].population = 100
        districts[4].population = 50
        districts[5].population = 50
        assert v.validateDistrict(districts[1])
        assert v.validateDistrict(districts[2])
        assert v.validateDistrict(districts[3])
        assert v.validateDistrict(districts[4])
        assert v.validateDistrict(districts[5])
