# -*- coding: utf-8 -*-
"""District manager

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
    Any,
    Iterable,
    Optional,
    OrderedDict,
    Union,
    overload
)

from qgis.PyQt.QtCore import (
    QObject,
    QSignalMapper,
    pyqtSignal
)

from ..utils import tr
from .base import BaseModel
from .District import (
    RdsDistrict,
    RdsUnassigned
)


class DistrictList(BaseModel):
    districtNameChanged = pyqtSignal(QObject)
    districtMembersChanged = pyqtSignal(QObject)
    districtDescriptionChanged = pyqtSignal(QObject)

    class _IndexAccessor:
        def __init__(self, lst: "DistrictList"):
            self._list = lst

        @overload
        def __getitem__(self, index: tuple) -> Any:
            pass

        @overload
        def __getitem__(self, index: int) -> RdsDistrict:
            pass

        def __getitem__(self, index):
            if isinstance(index, tuple):
                index, field = index
            else:
                field = None

            if isinstance(index, int):
                district = list(self._list._districts.values())[index]

                if field is not None:
                    return district[field]

                return district

            raise IndexError(tr("Invalid index to DistrictList.byindex"))

    class _NameAccessor:
        def __init__(self, lst: "DistrictList"):
            self._list = lst

        @overload
        def __getitem__(self, index: tuple) -> Any:
            pass

        @overload
        def __getitem__(self, index: str) -> RdsDistrict:
            pass

        def __getitem__(self, index):
            if isinstance(index, tuple):
                index, field = index
            else:
                field = None

            if isinstance(index, str):
                for district in self._list._districts.values():
                    if district.name == index:
                        break
                else:
                    raise KeyError(tr("District name not found: {name}").format(name=index))

                if field is not None:
                    return district[field]

                return district

            raise KeyError(tr("Invalid key passed to DistrictList.byname"))

    def __init__(self, numDistricts=0, districts: Optional[Iterable[RdsDistrict]] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._nameSignalMapper = QSignalMapper(self)
        self._nameSignalMapper.mappedObject.connect(self.districtNameChanged)
        self._membersSignalMapper = QSignalMapper(self)
        self._membersSignalMapper.mappedObject.connect(self.districtMembersChanged)
        self._descripSignalMapper = QSignalMapper(self)
        self._descripSignalMapper.mappedObject.connect(self.districtDescriptionChanged)

        self._indexaccessor = DistrictList._IndexAccessor(self)
        self._nameaccessor = DistrictList._NameAccessor(self)
        self._numDistricts = numDistricts

        if districts is not None:
            self._districts: dict[int, RdsDistrict] = OrderedDict()
            for d in districts:
                if d.district == 0:
                    self._districts[0] = d
                else:
                    self.add(d)
        else:
            self._districts: dict[int, RdsDistrict] = OrderedDict({0: RdsUnassigned()})

    def clone(self, districts: Optional[Iterable[RdsDistrict]] = None):
        if districts is None:
            districts = self._districts.values()

        instance = self.__class__(self._numDistricts, [d.clone() for d in districts])
        return instance

    @ overload
    def __getitem__(self, index: int) -> RdsDistrict:
        ...

    @ overload
    def __getitem__(self, index: slice) -> "DistrictList":
        ...

    @ overload
    def __getitem__(self, index: tuple) -> Any:
        ...

    def __getitem__(self, index):
        if isinstance(index, tuple):
            index, field = index
            if not isinstance(field, (str, int)):
                raise ValueError(tr("Field index to DistrictList must be a str or int"))
        else:
            field = None

        if isinstance(index, int):
            if field is not None:
                return self._districts[index][field]

            return self._districts[index]

        if isinstance(index, slice):
            if field is not None:
                return [d[field] for d in list(self._districts.values())[index]]
            return self.__class__(self._numDistricts, list(self._districts.values())[index])

        raise ValueError(tr("Invalid index to DistrictList"))

    def __iter__(self):
        for d in self._districts.values():
            yield d

    def __len__(self):
        return len(self._districts)

    @overload
    def __contains__(self, index: RdsDistrict) -> bool:
        ...

    @overload
    def __contains__(self, index: int) -> bool:
        ...

    def __contains__(self, index) -> bool:
        if isinstance(index, RdsDistrict):
            return index.district in self._districts

        return index in self._districts

    def __bool__(self) -> bool:
        return bool(self._districts)

    def keys(self):
        return self._districts.keys()

    def values(self):
        return self._districts.values()

    def items(self):
        return self._districts.items()

    def index(self, district: RdsDistrict):
        return list(self._districts.values()).index(district)

    def clear(self):
        newdict = OrderedDict()
        if 0 in self._districts:
            newdict[0] = RdsUnassigned()
            del self._districts[0]

        for d in self._districts.values():
            d.nameChanged.disconnect(self._nameSignalMapper.map)
            d.membersChanged.disconnect(self._membersSignalMapper.map)
            d.descriptionChanged.disconnect(self._descripSignalMapper.map)
            self._nameSignalMapper.removeMappings(d)
            self._membersSignalMapper.removeMappings(d)
            self._descripSignalMapper.removeMappings(d)

        self._districts = newdict

    def add(self, district: RdsDistrict):
        assert 0 < district.district <= self.numDistricts
        self._nameSignalMapper.setMapping(district, district)
        self._membersSignalMapper.setMapping(district, district)
        self._descripSignalMapper.setMapping(district, district)
        district.nameChanged.connect(self._nameSignalMapper.map)
        district.membersChanged.connect(self._membersSignalMapper.map)
        district.descriptionChanged.connect(self._descripSignalMapper.map)

        self._districts[district.district] = district
        self._districts = {key: self._districts[key] for key in sorted(self._districts.keys())}

    def remove(self, district: Union[RdsDistrict, int]):
        if isinstance(district, int):
            if district in self._districts:
                district = self._districts[district]

        # attempt to remove Unassigned raises error unless list is a slice that excludes Unassigned
        if district.district == 0 and 0 in self._districts:
            raise ValueError(tr("Cannot remove Unassigned"))

        if district.district in self._districts:
            district.nameChanged.disconnect(self._nameSignalMapper.map)
            district.membersChanged.disconnect(self._membersSignalMapper.map)
            district.descriptionChanged.disconnect(self._descripSignalMapper.map)
            self._nameSignalMapper.removeMappings(district)
            self._membersSignalMapper.removeMappings(district)
            self._descripSignalMapper.removeMappings(district)
            del self._districts[district.district]
        else:
            raise ValueError(tr("District {district} not found in District List").format(district=district.district))

    numDistricts: int

    @property
    def numDistricts(self) -> int:
        return self._numDistricts

    @numDistricts.setter
    def numDistricts(self, value: int):
        assert value > 1
        self._numDistricts = value

    @property
    def byindex(self):
        return self._indexaccessor

    @property
    def byname(self):
        return self._nameaccessor
