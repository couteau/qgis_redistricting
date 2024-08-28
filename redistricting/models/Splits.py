from typing import (
    Any,
    Sequence,
    Union
)

import pandas as pd
from qgis.PyQt.QtCore import pyqtSignal

from .base import (
    MISSING,
    Factory,
    RdsBaseModel,
    rds_property
)
from .Field import RdsGeoField


class RdsSplitDistrict:
    def __init__(self, data: pd.DataFrame, idx: tuple[str, int]):
        self._data = data
        self._idx = idx

    @property
    def geoid(self) -> str:
        return self._idx[0]

    @property
    def district(self) -> int:
        return self._idx[1]

    @property
    def attributes(self) -> Sequence[Any]:
        return self

    def __len__(self) -> int:
        return len(self._data.columns) + 1 - int("__name" in self._data.columns)

    def __getitem__(self, index: str):
        if index == 0:
            return self.district
        else:
            col = self._data.columns[index-1]
            return self._data.loc[self._idx, col]


class RdsSplitGeography:
    def __init__(self, data: pd.DataFrame, geoid: str):
        self._data = data
        self._geoid = geoid
        self._districts = data.loc[geoid].index
        self._splits = [
            RdsSplitDistrict(data, (geoid, d)) for d in self._districts
        ]
        self.attributes = [
            f"{self.name} ({self.geoid})" if "__name" in self._data.columns else self.geoid, ", ".join(self._districts)]

    def __len__(self):
        return len(self._districts)

    def __getitem__(self, index) -> RdsSplitDistrict:
        return self._districts[index]

    @property
    def geoid(self):
        return self._geoid

    @property
    def districts(self):
        return self._districts

    @property
    def name(self):
        if "__name" in self._data.columns:
            i = self._data.columns.get_loc("__name",)
            return self._data.loc[self._geoid].iat[0, i]

        return ""


class RdsSplits(RdsBaseModel):
    splitUpdating = pyqtSignal()
    splitUpdated = pyqtSignal()

    field: str
    data: pd.DataFrame = Factory(pd.DataFrame, False)
    geoField: RdsGeoField = rds_property(private=True, serialize=False, default=None)

    def __init__(self, field: Union[str, RdsGeoField], data: pd.DataFrame = MISSING):
        if isinstance(field, RdsGeoField):
            super().__init__(field=field.field, data=data)
            self.geoField = field
        else:
            super().__init__(field=field, data=data)

    def __post_init__(self, **kwargs):
        if self.data is not None:
            self.makeSplits()
        else:
            self.splits = []

    def __key__(self):
        return self.field

    def makeSplits(self):
        if self.data is None:
            self.splits = []
            return

        self.splits = [
            RdsSplitGeography(self.data, geoid)
            for geoid in self.data.index.get_level_values(0).unique()
        ]

    def setData(self, data: pd.DataFrame):
        self.splitUpdating.emit()
        self.data = data
        self.makeSplits()
        self.splitUpdated.emit()
