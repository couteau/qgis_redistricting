from collections.abc import Iterable
from typing import TYPE_CHECKING

import pandas as pd

from ..utils import tr
from .base.lists import KeyedList
from .base.model import Factory
from .consts import DistrictColumns
from .metricslist import MetricLevel, MetricTriggers, RdsMetric, register_metrics
from .splits import RdsSplits

if TYPE_CHECKING:
    from .field import RdsGeoField
    from .plan import RdsPlan

class RdsSplitsMetric(RdsMetric[KeyedList[RdsSplits]],
                      mname="splits",
                      level=MetricLevel.GEOGRAPHIC,
                      triggers=MetricTriggers.ON_UPDATE_GEOMETRY | MetricTriggers.ON_UPDATE_DEMOGRAPHICS):

    value = RdsMetric.value.factory(Factory(KeyedList[RdsSplits], with_owner=False), override=True)

    def __pre_init__(self):
        self.data: dict[str, pd.DataFrame] = {}

    def getSplitNames(self, field: 'RdsGeoField', geoids: Iterable[str]):
        return {g: field.getName(g) for g in geoids}

    def calculate(self, populationData: pd.DataFrame, geometry, plan: 'RdsPlan', **depends):
        if plan is None:
            self._value: KeyedList[RdsSplits] = KeyedList[RdsSplits]()
            self.data: dict[str, pd.DataFrame] = {}
            return

        if populationData is not None:
            cols = [plan.distField]
            if DistrictColumns.POPULATION in populationData.columns:
                cols += [DistrictColumns.POPULATION] + \
                    [f.fieldName for f in plan.popFields] + \
                    [f.fieldName for f in plan.dataFields]

            self.data = {}
            for field in plan.geoFields:
                g = populationData.dropna(subset=[field.fieldName])[[field.fieldName] + cols].groupby([field.fieldName])
                splits_data = g.filter(lambda x: x[plan.distField].nunique() > 1)

                splitpop = splits_data[[field.fieldName] + cols] \
                    .groupby([field.fieldName, plan.distField]) \
                    .sum()

                if field.nameField and field.getRelation() is not None:
                    name_map = self.getSplitNames(field, splitpop.index.get_level_values(0).unique())
                    names = pd.Series(name_map.values(), index=name_map.keys(), name="__name", dtype=str)

                    splitpop = splitpop \
                        .reset_index(level=1) \
                        .join(names) \
                        .set_index('district', append=True) \
                        .sort_values(by="__name")
                else:
                    splitpop = splitpop.sort_index()

                self.data[field.fieldName] = splitpop

    def finished(self, plan: 'RdsPlan'):    
        new_splits: KeyedList[RdsSplits] = KeyedList[RdsSplits]()

        for f, split in self.data.items():
            if f not in self._value:
                new_splits[f] = RdsSplits(f, split)
                new_splits[f].caption = plan.geoFields[f].caption
                plan.geoFields[f].captionChanged.connect(new_splits[f].updateCaption)
            else:
                new_splits[f] = self._value[f]
                new_splits[f].setData(split)

        self._value = new_splits
        self.data: dict[str, pd.DataFrame] = {}

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        if idx is None:
            return repr({k: len(v) for k, v in self._value.items()})

        if idx not in self._value:
            return ""

        return f"{len(self._value[idx]):,}"

    def tooltip(self, idx=None):
        return tr('Double-click or press enter to see split details')

register_metrics([RdsSplitsMetric])