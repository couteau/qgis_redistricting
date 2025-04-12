import math
from collections.abc import (
    Iterable,
    Sequence
)
from itertools import repeat
from statistics import (
    StatisticsError,
    mean
)

import geopandas as gpd
import pandas as pd
import pyproj
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

from ..utils import (
    spatialite_connect,
    tr
)
from .base.lists import KeyedList
from .columns import (
    ConstStr,
    DistrictColumns,
    MetricsColumns
)
from .field import RdsGeoField
from .metricslist import (
    MetricLevel,
    MetricTriggers,
    RdsAggregateMetric,
    RdsMetric,
    register_metrics
)
from .plan import (
    DeviationType,
    RdsPlan
)
from .splits import RdsSplits
from .validators import validators

# pylint: disable=unused-argument


class RdsTotalPopulationMetric(RdsMetric[int],
                               mname="totalPopulation",
                               level=MetricLevel.PLANWIDE,
                               triggers=MetricTriggers.ON_CREATE_PLAN):

    def caption(self):
        return DistrictColumns.POPULATION.comment

    def calculate(self, populationData: pd.DataFrame, geometry: gpd.GeoSeries, **depends):
        if populationData is not None:
            self._value = int(populationData[DistrictColumns.POPULATION].sum())

    def value(self) -> int:
        return self._value

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        return f"{self._value:,}"


class RdsDeviationMetric(RdsMetric[pd.Series],
                         mname="deviation",
                         level=MetricLevel.DISTRICT,
                         triggers=MetricTriggers.ON_UPDATE_DEMOGRAPHICS,
                         depends=(RdsTotalPopulationMetric,)):

    def caption(self):
        return DistrictColumns.DEVIATION.comment

    def calculate(self, populationData: pd.DataFrame, geometry: gpd.GeoSeries, *, totalPopulation: int = 0, **depends):
        if populationData is not None:
            members = pd.Series(
                [
                    None if d == 0
                    else d.members
                    for d in self.plan.districts
                ],
                index=(d.district for d in self.plan.districts),
                dtype="Int64"
            )

            ideal = round(totalPopulation / self.plan.numSeats)

            self._value = \
                populationData[[self.plan.distField, DistrictColumns.POPULATION]] \
                .groupby(self.plan.distField) \
                .sum()[DistrictColumns.POPULATION] \
                .sub(members * ideal)

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        if idx is None:
            return f"{', '.join(f'{v:+,}' for v in self._value)}"

        if idx not in self._value:
            return ""

        return f"{self._value[idx]:+,}"


class RdsPctDeviationMetric(RdsMetric[pd.Series],
                            mname="pctDeviation",
                            level=MetricLevel.DISTRICT,
                            triggers=MetricTriggers.ON_UPDATE_DEMOGRAPHICS,
                            depends=(RdsTotalPopulationMetric, RdsDeviationMetric)):

    def caption(self):
        return DistrictColumns.PCT_DEVIATION.comment

    def calculate(
        self,
        populationData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        *,
        totalPopulation: int = 0,
        deviation: pd.Series = None,
        **depends
    ):
        if deviation is None:
            self._value = None
            return

        if totalPopulation == 0:
            self._value = pd.Series(0, deviation.index())
        else:
            idealPerMember = round(totalPopulation / self.plan.numSeats)
            districtIdeal = pd.Series(
                [
                    None if d.district == 0
                    else d.members * idealPerMember
                    for d in self.plan.districts
                ],
                index=(d.district for d in self.plan.districts),
                dtype="Int64"
            )

            self._value = deviation / districtIdeal

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        if idx is None:
            return f"{', '.join(f'{v:+.2%}' for v in self._value)}"

        if idx not in self._value:
            return ""

        return f"{self._value[idx]:+.2%}"


class RdsPlanDeviationMetric(RdsAggregateMetric[tuple[float, float]],
                             mname="planDeviation",
                             level=MetricLevel.PLANWIDE,
                             triggers=MetricTriggers.ON_UPDATE_DEMOGRAPHICS,
                             values=RdsPctDeviationMetric):

    def caption(self):
        return DistrictColumns.PCT_DEVIATION.comment

    def aggregate(self, populationData, geometry, values: pd.Series):
        return float(values.min()), float(values.max())

    def format(self, idx=None):
        if self._value is None:
            return None

        minDeviation, maxDeviation = self._value
        if minDeviation is None or maxDeviation is None:
            result = ""
        else:
            result = f"{maxDeviation:+.2%}, {minDeviation:+.2%}" \
                if self.plan.deviationType == DeviationType.OverUnder \
                else f"{maxDeviation-minDeviation:.2%}"

        return result

    def isValid(self) -> bool:
        validator = validators[self.plan.deviationType](self.plan)
        return validator.validatePlan()

    def forgroundColor(self, idx=None):
        return QColor(Qt.GlobalColor.red) if not self.isValid() else QColor(Qt.GlobalColor.green)


class CeaProjMetric(RdsMetric[gpd.GeoSeries],
                    mname="cea_proj",
                    level=MetricLevel.DISTRICT,
                    triggers=MetricTriggers.ON_UPDATE_GEOMETRY,
                    display=False,
                    serialize=False
                    ):
    def calculate(self, populationData: pd.DataFrame, geometry: gpd.GeoSeries, **depends):
        cea_crs = pyproj.CRS('+proj=cea')
        self._value: gpd.GeoSeries = geometry.geometry.to_crs(cea_crs)


class DistrictAggregateMixin:
    def __init_subclass__(cls, *, level=MetricLevel.PLANWIDE, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._level = level


class DistrictMeanMixin(DistrictAggregateMixin):
    def aggregate(self, populationData, geometry, values):
        if isinstance(values, pd.Series):
            return float(values[values.index != 0].mean())

        if isinstance(values, Sequence):
            values = values[1:]

        try:
            return mean(v for v in values if v is not None)
        except StatisticsError:
            return None

    @classmethod
    def short_name(cls):
        return tr("Mean")


class DistrictMinMixin(DistrictAggregateMixin):
    def aggregate(self, populationData, geometry, values):
        if isinstance(values, pd.Series):
            return float(values[values.index != 0].min())

        if isinstance(values, Sequence):
            values = values[1:]

        return min(v for v in values if v is not None)

    @classmethod
    def short_name(cls):
        return tr("Min.")


class DistrictMaxMixin(DistrictAggregateMixin):
    def aggregate(self, populationData, geometry, values):
        if isinstance(values, pd.Series):
            return float(values[values.index != 0].max())

        if isinstance(values, Sequence):
            values = values[1:]

        return max(v for v in values if v is not None)

    @classmethod
    def short_name(cls):
        return tr("Max.")


class DistrictSumMixin(DistrictAggregateMixin):
    def aggregate(self, populationData, geometry, values):
        if isinstance(values, pd.Series):
            return float(values[values.index != 0].sum())

        if isinstance(values, Sequence):
            values = values[1:]

        return sum(v for v in values if v is not None)

    @classmethod
    def short_name(cls):
        return tr("Total")


class RdsCompactnessMetric(RdsMetric[float], mname="__compactness"):
    def __init_subclass__(cls,
                          score: ConstStr,
                          group=tr("Compactness"),
                          level=MetricLevel.DISTRICT,
                          triggers=MetricTriggers.ON_UPDATE_GEOMETRY,
                          depends=(CeaProjMetric,),
                          **kwargs):
        super().__init_subclass__(mname=score, group=group, level=level, triggers=triggers, depends=depends, **kwargs)
        cls._score = score

    @RdsMetric.plan.setter
    def plan(self, value: RdsPlan):
        RdsMetric.plan.__set__(self, value)  # pylint: disable=unnecessary-dunder-call
        numDistricts = value.numDistricts + 1 if value is not None else 1
        self._value = pd.Series(
            data=repeat(0, numDistricts),
            index=pd.RangeIndex(numDistricts)
        )

    def caption(self):
        return self._score.comment

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        return f"{self._value:.3f}"


class RdsCompactnessAggregate(RdsAggregateMetric[float], mname="__compactnessagg", values=None):
    def __init_subclass__(cls,
                          mname,
                          values: RdsCompactnessMetric,
                          triggers=MetricTriggers.ON_UPDATE_GEOMETRY,
                          group=tr("Compactness"),
                          **kwargs):
        super().__init_subclass__(mname=mname, group=group, triggers=triggers, values=values, **kwargs)

    def caption(self):
        return tr("{short_name} {caption}").format(
            short_mname=self.short_name(), caption=self._source_metric.caption()
        )

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        return f"{self._value:.3f}"


class RdsPolsbyPopper(RdsCompactnessMetric, score=MetricsColumns.POLSBYPOPPER):
    def calculate(self, populationData, geometry: gpd.GeoSeries, *, cea_proj: gpd.GeoSeries = None, **depends):
        if cea_proj is None:
            self._value = pd.Series(0, geometry.index)
        self._value = 4 * math.pi * cea_proj.area / (cea_proj.length**2)


class RdsMeanPolsbyPopper(DistrictMeanMixin, RdsCompactnessAggregate,
                          mname=f"mean{MetricsColumns.POLSBYPOPPER.capitalize()}",
                          display=False,
                          values=RdsPolsbyPopper):
    ...


class RdsMinPolsbyPopper(DistrictMinMixin, RdsCompactnessAggregate,
                         mname=f"min{MetricsColumns.POLSBYPOPPER.capitalize()}",
                         display=False,
                         values=RdsPolsbyPopper):
    ...


class RdsMaxPolsbyPopper(DistrictMaxMixin, RdsCompactnessAggregate,
                         mname=f"max{MetricsColumns.POLSBYPOPPER.capitalize()}",
                         display=False,
                         values=RdsPolsbyPopper):
    ...


class RdsAggScores(RdsMetric, mname="__agg_compactness", level=MetricLevel.PLANWIDE):
    def __init_subclass__(cls,
                          score: ConstStr,
                          triggers=MetricTriggers.ON_UPDATE_GEOMETRY,
                          group=tr("Compactness"),
                          **kwargs):
        super().__init_subclass__(mname=f"agg{score.capitalize()}",
                                  group=group, triggers=triggers, serialize=False,
                                  **kwargs)
        cls._score = score

    def calculate(self, populationData, geometry, **depends):
        self._value: dict[type[RdsAggregateMetric], float] = {d: depends[d.name()] for d in self.depends()}

    def caption(self):
        if self._value is None:
            return self._score.comment

        return f"{self._score.comment} ({', '.join(d.short_name() for d in self._value.keys())})"

    def format(self, idx=None):
        if self._value is None:
            return None

        return ", ".join(f"{v:0.3f}" for v in self._value.values())


class RdsAggPolsbyPopper(RdsAggScores,
                         score=MetricsColumns.POLSBYPOPPER,
                         depends=(RdsMeanPolsbyPopper, RdsMinPolsbyPopper, RdsMaxPolsbyPopper)):

    ...


class RdsReock(RdsCompactnessMetric, score=MetricsColumns.REOCK):
    def calculate(self, populationData, geometry, *, cea_proj: gpd.GeoSeries = None, **depends):
        if cea_proj is None:
            self._value = pd.Series(0, geometry.index)
        self._value = cea_proj.area / cea_proj.minimum_bounding_circle().area


class RdsMeanReock(DistrictMeanMixin, RdsCompactnessAggregate,
                   mname=f"mean{MetricsColumns.REOCK.capitalize()}",
                   display=False,
                   values=RdsReock):
    ...


class RdsMinReock(DistrictMinMixin, RdsCompactnessAggregate,
                  mname=f"min{MetricsColumns.REOCK.capitalize()}",
                  display=False,
                  values=RdsReock):
    ...


class RdsMaxReock(DistrictMaxMixin, RdsCompactnessAggregate,
                  mname=f"max{MetricsColumns.REOCK.capitalize()}",
                  display=False,
                  values=RdsReock):
    ...


class RdsAggReock(RdsAggScores,
                  score=MetricsColumns.REOCK,
                  depends=(RdsMeanReock, RdsMinReock, RdsMaxReock)):
    ...


class RdsConvexHull(RdsCompactnessMetric, score=MetricsColumns.CONVEXHULL):
    def calculate(self, populationData, geometry, *, cea_proj: gpd.GeoSeries = None, **depends):
        if cea_proj is None:
            self._value = pd.Series(0, geometry.index)
        self._value = cea_proj.area / cea_proj.convex_hull.area

# pylint: disable=no-member


class RdsMeanConvexHull(DistrictMeanMixin, RdsCompactnessAggregate,
                        mname=f"mean{MetricsColumns.CONVEXHULL.capitalize()}",
                        display=False,
                        values=RdsConvexHull):
    ...


class RdsMinConvexHull(DistrictMinMixin, RdsCompactnessAggregate,
                       mname=f"min{MetricsColumns.CONVEXHULL.capitalize()}",
                       display=False,
                       values=RdsConvexHull):
    ...


class RdsMaxConvexHull(DistrictMaxMixin, RdsCompactnessAggregate,
                       mname=f"max{MetricsColumns.CONVEXHULL.capitalize()}",
                       display=False,
                       values=RdsConvexHull):
    ...


class RdsAggConvexHull(RdsAggScores,
                       score=MetricsColumns.CONVEXHULL,
                       depends=(RdsMeanConvexHull, RdsMinConvexHull, RdsMaxConvexHull)):
    ...


class RdsCutEdges(RdsMetric[int],
                  mname="cutEdges",
                  group=tr("Compactness"),
                  level=MetricLevel.PLANWIDE,
                  triggers=MetricTriggers.ON_UPDATE_GEOMETRY):

    def caption(self):
        return tr("Cut Edges")

    def calculate(self, populationData: pd.DataFrame, geometry: gpd.GeoSeries, **depends):
        with spatialite_connect(self.plan.geoPackagePath) as db:
            # select count of unit pairs where
            #   1) assigned districts are different (also takes care of excluding unassigned units from count),
            #   2) combination is unique (count a,b but not b,a),
            #   3) bounding boxes touch or overlap (using spatial index to minimize more intensive adjacency checks)
            #   4) units are adjacent at more than a point
            sql = f"""SELECT count(*)
                FROM assignments a JOIN assignments b
                ON b.{self.plan.distField} != a.{self.plan.distField} AND b.{self.plan.geoIdField} > a.{self.plan.geoIdField}
                AND b.fid IN (
                    SELECT id FROM rtree_assignments_geometry r
                    WHERE r.minx <= st_maxx(a.geometry) and r.maxx >= st_minx(a.geometry)
                    AND r.miny <= st_maxy(a.geometry) and r.maxy >= st_miny(a.geometry)
                )
                AND st_relate(a.geometry, b.geometry, 'F***1****')"""

            c = db.execute(sql)
            self._value = c.fetchone()[0]

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        return f"{self._value:,}"


class RdsSplitsMetric(RdsMetric[KeyedList[RdsSplits]],
                      mname="splits",
                      level=MetricLevel.GEOGRAPHIC,
                      triggers=MetricTriggers.ON_UPDATE_GEOMETRY | MetricTriggers.ON_UPDATE_DEMOGRAPHICS):

    def __init__(self, plan: RdsPlan = None):
        self._value: KeyedList[RdsSplits] = KeyedList()
        self.data: dict[str, pd.DataFrame] = {}
        super().__init__(plan)

    @RdsMetric.plan.setter
    def plan(self, value: RdsPlan):
        RdsMetric.plan.__set__(self, value)  # pylint: disable=unnecessary-dunder-call
        if value is not None:
            self.updateGeoFields(value.geoFields)

    def updateGeoFields(self, geoFields: Iterable[RdsGeoField]):
        splits: KeyedList[RdsSplits] = KeyedList([RdsSplits(f) for f in geoFields])
        for split in splits.values():
            if split.field in self._value:
                split.setData(self._value[split.field].data)

        self._value = splits

    def getSplitNames(self, field: 'RdsGeoField', geoids: Iterable[str]):
        return {g: field.getName(g) for g in geoids}

    def calculate(self, populationData: pd.DataFrame, geometry: gpd.GeoSeries, **depends):
        cols = [self.plan.distField]
        if DistrictColumns.POPULATION in populationData.columns:
            cols += [DistrictColumns.POPULATION] + \
                [f.fieldName for f in self.plan.popFields] + \
                [f.fieldName for f in self.plan.dataFields]

        self.data = {}
        for field in self.plan.geoFields:
            g = populationData.dropna(subset=[field.fieldName])[[field.fieldName] + cols].groupby([field.fieldName])
            splits_data = g.filter(lambda x: x[self.plan.distField].nunique() > 1)

            splitpop = splits_data[[field.fieldName] + cols] \
                .groupby([field.fieldName, self.plan.distField]) \
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

    def updateSplits(self, data: dict[str, pd.DataFrame]):
        new_splits: KeyedList[RdsSplits] = KeyedList()

        for f, split in data.items():
            if f not in self._value:
                new_splits[f] = RdsSplits(f, split)
                new_splits[f].geoField = self._plan.geoFields[f]
            else:
                new_splits[f] = self._value[f]
                new_splits[f].setData(split)

        self._value = new_splits

    def finished(self):
        self.updateSplits(self.data)
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


class RdsBoolMetric(RdsMetric[bool], mname="__boolmetric"):
    def format(self, idx=None):
        if self._value is None:
            return None

        return tr("YES") if self._value else "NO"

    def forgroundColor(self, idx=None) -> QColor:
        return QColor(Qt.green) if self._value else QColor(Qt.red)


class RdsContiguityMetric(RdsBoolMetric, mname="contiguity", triggers=MetricTriggers.ON_UPDATE_GEOMETRY):
    def calculate(self, populationData: pd.DataFrame, geometry: gpd.GeoSeries, **depends):
        if len(self.plan.districts) == 1:
            self._value = None
            return

        self._value = geometry[geometry.index != 0].count_geometries().sum() == self.plan.allocatedDistricts

    def tooltip(self, idx=None):
        if self._value:
            return None

        return tr('Plan contains non-contiguous districts\nDouble-click or press enter for details')


class RdsCompleteMetric(RdsBoolMetric, mname="complete", triggers=MetricTriggers.ON_UPDATE_GEOMETRY):
    def calculate(self, populationData: pd.DataFrame, geometry: gpd.GeoSeries, **depends):
        self._value = populationData[populationData[self.plan.distField] == 0].empty

    def tooltip(self, idx=None):
        if self._value:
            return None

        return tr('Plan contains unassigned geography\nDouble-click or press enter for details')


register_metrics([RdsTotalPopulationMetric, RdsDeviationMetric, RdsPctDeviationMetric, RdsPlanDeviationMetric], True)
register_metrics([CeaProjMetric, RdsPolsbyPopper, RdsReock, RdsConvexHull, RdsCutEdges,
                  RdsMeanPolsbyPopper, RdsMinPolsbyPopper, RdsMaxPolsbyPopper,
                  RdsMeanReock, RdsMinReock, RdsMaxReock,
                  RdsMeanConvexHull, RdsMinConvexHull, RdsMaxConvexHull,
                  RdsSplitsMetric, RdsContiguityMetric, RdsCompleteMetric,
                  RdsAggPolsbyPopper, RdsAggReock, RdsAggConvexHull])
