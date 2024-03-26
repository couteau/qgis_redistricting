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
    Optional,
    overload
)

from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from ..utils import tr
from .District import (
    District,
    Unassigned
)


class DistrictList(QObject):
    districtChanged = pyqtSignal('PyQt_PyObject')

    class _IndexAccessor:
        def __init__(self, lst: "DistrictList"):
            self._list = lst

        @overload
        def __getitem__(self, index: tuple) -> Any:
            pass

        @overload
        def __getitem__(self, index: int) -> District:
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
        def __getitem__(self, index: str) -> District:
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

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._districts: dict[int, District] = {0: Unassigned()}
        self._indexaccessor = DistrictList._IndexAccessor(self)
        self._nameaccessor = DistrictList._NameAccessor(self)
        self._numDistricts = 0

    # pylint: disable=protected-access
    @classmethod
    def clone(cls, from_list: "DistrictList", districts: Optional[list[District]] = None, parent: Optional[QObject] = None):
        instance = cls(parent)
        if districts is not None:
            instance._districts = {d.district: d for d in districts}
        instance._numDistricts = from_list._numDistricts
        return instance
    # pylint: enable=protected-access

    @overload
    def __getitem__(self, index: int) -> District:
        ...

    @overload
    def __getitem__(self, index: slice) -> "DistrictList":
        ...

    @overload
    def __getitem__(self, index: tuple) -> Any:
        ...

    def __getitem__(self, index):
        if isinstance(index, tuple):
            index, field = index
            if not isinstance(field, str):
                raise ValueError(tr("Field index to DistrictList must be a string"))
        else:
            field = None

        if isinstance(index, int):
            if field is not None:
                return self._districts[index][field]

            return self._districts[index]

        if isinstance(index, slice):
            if field is not None:
                return [d[field] for d in list(self._districts.values())[index]]

            return DistrictList.clone(self, list(self._districts.values())[index])

        raise ValueError(tr("Invalid index to DistrictList"))

    def __iter__(self):
        for d in self._districts.values():
            yield d

    def __len__(self):
        return len(self._districts)

    def __contains__(self, index):
        if isinstance(index, District):
            return index.district in self._districts

        return index in self._districts

    def __bool__(self) -> bool:
        return len(self._districts) == 1 and 0 in self._districts

    def keys(self):
        return self._districts.keys()

    def values(self):
        return self._districts.values()

    def items(self):
        return self._districts.items()

    def index(self, district: District):
        return list(self._districts.values()).index(district)

    def clear(self):
        self._districts = {0: Unassigned()}

    def append(self, district: District):
        assert 0 < district.district <= self.numDistricts
        self._districts[district.district] = district

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

    # stats
    def _avgScore(self, score: str):
        return sum(d[score] for d in self._districts.values() if d.district != 0) / (len(self._districts) - 1)

    @property
    def avgPolsbyPopper(self):
        return self._avgScore("polsbypopper")

    @property
    def avgReock(self):
        return self._avgScore("reock")

    @property
    def avgConvexHull(self):
        return self._avgScore("convexhull")
