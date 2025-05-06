"""QGIS Redistricting Plugin - split geography models

        begin                : 2024-09-15
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

from abc import abstractmethod
from functools import partial
from typing import Any, Optional, Sequence, Union

import pandas as pd
from qgis.PyQt.QtCore import pyqtSignal

from .base.model import RdsBaseModel
from .base.prop import Factory, rds_property


class RdsSplitBase:
    def __init__(
        self, parent: Union["RdsSplitBase", "RdsSplits"], data: pd.DataFrame, idx: Union[str, tuple[str, int]]
    ):
        self._parent = parent
        self._data = data
        self._idx = idx

    @property
    @abstractmethod
    def attributes(self) -> Sequence[Any]:
        return NotImplemented

    @property
    def parent(self):
        return self._parent


class RdsSplitDistrict(RdsSplitBase):
    def __len__(self) -> int:
        return len(self._data.columns) + 1 - int("__name" in self._data.columns)

    def __getitem__(self, index: int):
        if index == 0:
            return self.district

        if 0 < index < len(self._data.columns):
            col = self._data.columns[index - 1]
            return self._data.loc[self._idx, col]

        raise IndexError()

    def __contains__(self, item):
        return item in self._data[self._idx]

    @property
    def geoid(self) -> str:
        return self._idx[0]

    @property
    def district(self) -> int:
        return self._idx[1]

    @property
    def attributes(self) -> Sequence[Any]:
        return self


class RdsSplitGeography(RdsSplitBase):
    def __init__(self, parent: "RdsSplits", data: pd.DataFrame, idx: str):
        super().__init__(parent, data, idx)
        self._districts = list(data.loc[idx].index)
        self._splits = [RdsSplitDistrict(self, data, (idx, d)) for d in self._districts]
        self._attributes = [
            f"{self.name} ({self.geoid})" if "__name" in self._data.columns else self.geoid,
            ", ".join(data.loc[idx].index.astype(str)),
        ]

    def __len__(self):
        return len(self._splits)

    def __getitem__(self, index) -> RdsSplitDistrict:
        return self._splits[index]

    @property
    def geoid(self):
        return self._idx

    @property
    def districts(self):
        return self._districts

    @property
    def name(self):
        if "__name" in self._data.columns:
            i = self._data.columns.get_loc(
                "__name",
            )
            return self._data.loc[self._idx].iat[0, i]

        return ""

    @property
    def attributes(self):
        return self._attributes


class RdsSplits(RdsBaseModel):
    splitUpdating = pyqtSignal()
    splitUpdated = pyqtSignal()

    field: str
    caption: str = rds_property(default=None)
    data: pd.DataFrame = Factory(partial(pd.DataFrame, index=pd.RangeIndex(0)), False)

    def __post_init__(self, **kwargs):
        if self.data is not None:
            self.makeSplits()
        else:
            self.splits = []

    def __len__(self):
        return len(self.splits)

    def __getitem__(self, index: int) -> RdsSplitGeography:
        return self.splits[index]

    def __key__(self):
        return self.field

    @caption.getter
    def caption(self):
        return self._caption or self.field.capitalize()

    @caption.setter
    def caption(self, value: Optional[str]):
        if value is None or value == self.field:
            self._caption = None
        else:
            self._caption = value

    def updateCaption(self):
        self.caption = self.sender().caption

    def index(self, item: RdsSplitGeography):
        if item.geoid not in self.data.index.get_level_values(0):
            raise IndexError(f"No split for {self.caption} {item.geoid!r}")

        return self.data.index.get_level_values(0).unique().get_loc(item.geoid)

    @property
    def attrCount(self):
        return len(self.data.columns) + 2 - int("__name" in self.data.columns)

    def makeSplits(self):
        if self.data is None:
            self.splits = []
            return

        self.splits = [
            RdsSplitGeography(self, self.data, geoid) for geoid in self.data.index.get_level_values(0).unique()
        ]

    def setData(self, data: pd.DataFrame):
        self.splitUpdating.emit()
        self.data = data
        self.makeSplits()
        self.splitUpdated.emit()
