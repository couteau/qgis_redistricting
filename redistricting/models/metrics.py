"""QGIS Redistricting Plugin - metrics classes

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

import math
from collections.abc import Mapping, Sequence
from statistics import StatisticsError, mean
from typing import TYPE_CHECKING, Optional, Union

import geopandas as gpd
import pandas as pd
import pyproj
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

from ..utils import spatialite_connect, tr
from ..utils.misc import quote_identifier
from .consts import ConstStr, DeviationType, DistrictColumns, MetricsColumns
from .metricslist import MetricLevel, MetricTriggers, RdsAggregateMetric, RdsMetric, register_metrics
from .validators import validators

if TYPE_CHECKING:
    from .plan import RdsPlan

# pylint: disable=unused-argument


class RdsTotalPopulationMetric(
    RdsMetric[int], mname="totalPopulation", level=MetricLevel.PLANWIDE, triggers=MetricTriggers.ON_CREATE_PLAN
):
    def caption(self):
        return DistrictColumns.POPULATION.comment

    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        **depends,
    ):
        if populationData is not None:
            self._value = int(populationData[DistrictColumns.POPULATION].sum())

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        return f"{self._value:,}"


class RdsDeviationMetric(
    RdsMetric[pd.Series],
    mname="deviation",
    level=MetricLevel.DISTRICT,
    triggers=MetricTriggers.ON_UPDATE_DEMOGRAPHICS,
    depends=(RdsTotalPopulationMetric,),
    field_type=int,
):
    def caption(self):
        return DistrictColumns.DEVIATION.comment

    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        *,
        totalPopulation: int = 0,
        **depends,
    ):
        if populationData is not None and plan is not None:
            idealPerMember = round(totalPopulation / plan.numSeats)

            self._value = (
                populationData[[plan.distField, DistrictColumns.POPULATION]]
                .groupby(plan.distField)
                .sum()[DistrictColumns.POPULATION]
                .sub(districtData["members"] * idealPerMember)
            )

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        if idx is None:
            return f"{', '.join(f'{v:+,}' for v in self._value)}"

        if idx not in self._value:
            return ""

        return f"{self._value[idx]:+,}"


class RdsPctDeviationMetric(
    RdsMetric[pd.Series],
    mname="pctDeviation",
    level=MetricLevel.DISTRICT,
    triggers=MetricTriggers.ON_UPDATE_DEMOGRAPHICS,
    depends=(RdsTotalPopulationMetric, RdsDeviationMetric),
    field_type=float,
):
    def caption(self):
        return DistrictColumns.PCT_DEVIATION.comment

    def calculate(  # noqa: PLR0913
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        *,
        totalPopulation: int = 0,
        deviation: pd.Series = None,
        **depends,
    ):
        if deviation is None or plan is None:
            self._value = None
            return

        if totalPopulation == 0:
            self._value = pd.Series(0, deviation.index)
        else:
            idealPerMember = round(totalPopulation / plan.numSeats)
            districtIdeal = districtData["members"] * idealPerMember

            self._value = deviation / districtIdeal

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        if idx is None:
            return f"{', '.join(f'{v:+.2%}' for v in self._value)}"

        if idx not in self._value:
            return ""

        return f"{self._value[idx]:+.2%}"


class RdsPlanDeviationMetric(
    RdsAggregateMetric[tuple[float, float]],
    mname="planDeviation",
    level=MetricLevel.PLANWIDE,
    triggers=MetricTriggers.ON_UPDATE_DEMOGRAPHICS,
    values=RdsPctDeviationMetric,
):
    formattedValue: str = ""
    valid: bool = True

    def caption(self):
        return DistrictColumns.PCT_DEVIATION.comment

    def aggregate(self, populationData, districtData, geometry, plan: "RdsPlan", values: pd.Series):
        minDeviation, maxDeviation = float(values[values.index != 0].min()), float(values[values.index != 0].max())
        self.formattedValue = (
            f"{maxDeviation:+.2%}, {minDeviation:+.2%}"
            if plan is None or plan.deviationType == DeviationType.OverUnder
            else f"{maxDeviation - minDeviation:.2%}"
        )
        if plan is not None:
            validator = validators[plan.deviationType](plan)
            self.valid = validator.validatePlan()
        else:
            self.valid = True
        return minDeviation, maxDeviation

    def format(self, idx=None):
        return self.formattedValue

    def forgroundColor(self, idx=None):
        return QColor(Qt.GlobalColor.red) if not self.valid else QColor(Qt.GlobalColor.green)


class CeaProjMetric(
    RdsMetric[gpd.GeoSeries],
    mname="cea_proj",
    level=MetricLevel.DISTRICT,
    triggers=MetricTriggers.ON_UPDATE_GEOMETRY,
    display=False,
    serialize=False,
):
    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        **depends,
    ):
        cea_crs = pyproj.CRS("+proj=cea")
        self._value: gpd.GeoSeries = geometry.geometry.to_crs(cea_crs)


class DistrictAggregateMixin:
    def __init_subclass__(cls, *, level=MetricLevel.PLANWIDE, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._level = level


class DistrictMeanMixin(DistrictAggregateMixin):
    def aggregate(self, populationData, districtData, geometry, plan: "RdsPlan", values):
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
    def aggregate(self, populationData, districtData, geometry, plan: "RdsPlan", values):
        if isinstance(values, pd.Series):
            return float(values[values.index != 0].min())

        if isinstance(values, Sequence):
            values = values[1:]

        return min(v for v in values if v is not None)

    @classmethod
    def short_name(cls):
        return tr("Min.")


class DistrictMaxMixin(DistrictAggregateMixin):
    def aggregate(self, populationData, districtData, geometry, plan: "RdsPlan", values):
        if isinstance(values, pd.Series):
            return float(values[values.index != 0].max())

        if isinstance(values, Sequence):
            values = values[1:]

        return max(v for v in values if v is not None)

    @classmethod
    def short_name(cls):
        return tr("Max.")


class DistrictSumMixin(DistrictAggregateMixin):
    def aggregate(self, populationData, districtData, geometry, plan: "RdsPlan", values):
        if isinstance(values, pd.Series):
            return float(values[values.index != 0].sum())

        if isinstance(values, Sequence):
            values = values[1:]

        return sum(v for v in values if v is not None)

    @classmethod
    def short_name(cls):
        return tr("Total")


# pylint: disable=abstract-method


class RdsCompactnessMetric(RdsMetric[pd.Series], mname="__compactness"):
    def __init_subclass__(  # noqa: PLR0913
        cls,
        score: ConstStr,
        group=tr("Compactness"),  # noqa: B008
        level=MetricLevel.DISTRICT,
        triggers=MetricTriggers.ON_UPDATE_GEOMETRY,
        depends=(CeaProjMetric,),
        field_type=float,
        **kwargs,
    ):
        super().__init_subclass__(
            mname=score, group=group, level=level, triggers=triggers, depends=depends, field_type=field_type, **kwargs
        )
        cls._score = score

    def __init__(self, value: Optional[Union[Mapping[int, float], Sequence[float]]] = None):
        if value is None:
            value = pd.Series(data=[0.0], index=pd.RangeIndex(1))
        elif isinstance(value, Mapping):
            value = pd.Series(value)
        else:
            value = pd.Series(data=value, index=pd.RangeIndex(len(value)))
        super().__init__(value)

    def caption(self):
        return self._score.comment

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        return f"{self._value:.3f}"


class RdsCompactnessAggregate(RdsAggregateMetric[float], mname="__compactnessagg", values=None):
    def __init_subclass__(
        cls,
        mname,
        values: RdsCompactnessMetric,
        triggers=MetricTriggers.ON_UPDATE_GEOMETRY,
        group=tr("Compactness"),  # noqa: B008
        **kwargs,
    ):
        super().__init_subclass__(mname=mname, group=group, triggers=triggers, values=values, **kwargs)

    def caption(self):
        return tr("{short_name} {caption}").format(short_mname=self.short_name(), caption=self._source_metric.caption())

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        return f"{self._value:.3f}"


# pylint: enable=abstract-method


class RdsPolsbyPopper(RdsCompactnessMetric, score=MetricsColumns.POLSBYPOPPER):
    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        *,
        cea_proj: gpd.GeoSeries = None,
        **depends,
    ):
        if cea_proj is None:
            self._value = pd.Series(0, geometry.index)
        self._value = 4 * math.pi * cea_proj.area / (cea_proj.length**2)


class RdsMeanPolsbyPopper(
    DistrictMeanMixin,
    RdsCompactnessAggregate,
    mname=f"mean{MetricsColumns.POLSBYPOPPER.capitalize()}",
    display=False,
    values=RdsPolsbyPopper,
): ...


class RdsMinPolsbyPopper(
    DistrictMinMixin,
    RdsCompactnessAggregate,
    mname=f"min{MetricsColumns.POLSBYPOPPER.capitalize()}",
    display=False,
    values=RdsPolsbyPopper,
): ...


class RdsMaxPolsbyPopper(
    DistrictMaxMixin,
    RdsCompactnessAggregate,
    mname=f"max{MetricsColumns.POLSBYPOPPER.capitalize()}",
    display=False,
    values=RdsPolsbyPopper,
): ...


class RdsAggScores(RdsMetric, mname="__agg_compactness", level=MetricLevel.PLANWIDE):
    def __init_subclass__(
        cls,
        score: ConstStr,
        triggers=MetricTriggers.ON_UPDATE_GEOMETRY,
        group=tr("Compactness"),  # noqa: B008
        **kwargs,
    ):
        super().__init_subclass__(
            mname=f"agg{score.capitalize()}", group=group, triggers=triggers, serialize=False, **kwargs
        )
        cls._score = score

    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        **depends,
    ):
        self._value: dict[type[RdsAggregateMetric], float] = {d: depends[d.name()] for d in self.depends()}

    def caption(self):
        if self._value is None:
            return self._score.comment

        return f"{self._score.comment} ({', '.join(d.short_name() for d in self._value.keys())})"

    def format(self, idx=None):
        if self._value is None or any(v is None for v in self._value.values()):
            return None

        return ", ".join(f"{v:0.3f}" for v in self._value.values())


class RdsAggPolsbyPopper(
    RdsAggScores,
    score=MetricsColumns.POLSBYPOPPER,
    depends=(RdsMeanPolsbyPopper, RdsMinPolsbyPopper, RdsMaxPolsbyPopper),
): ...


class RdsReock(RdsCompactnessMetric, score=MetricsColumns.REOCK):
    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        *,
        cea_proj: gpd.GeoSeries = None,
        **depends,
    ):
        if cea_proj is None:
            self._value = pd.Series(0, geometry.index)
        self._value = cea_proj.area / cea_proj.minimum_bounding_circle().area


class RdsMeanReock(
    DistrictMeanMixin,
    RdsCompactnessAggregate,
    mname=f"mean{MetricsColumns.REOCK.capitalize()}",
    display=False,
    values=RdsReock,
): ...


class RdsMinReock(
    DistrictMinMixin,
    RdsCompactnessAggregate,
    mname=f"min{MetricsColumns.REOCK.capitalize()}",
    display=False,
    values=RdsReock,
): ...


class RdsMaxReock(
    DistrictMaxMixin,
    RdsCompactnessAggregate,
    mname=f"max{MetricsColumns.REOCK.capitalize()}",
    display=False,
    values=RdsReock,
): ...


class RdsAggReock(RdsAggScores, score=MetricsColumns.REOCK, depends=(RdsMeanReock, RdsMinReock, RdsMaxReock)): ...


class RdsConvexHull(RdsCompactnessMetric, score=MetricsColumns.CONVEXHULL):
    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        *,
        cea_proj: gpd.GeoSeries = None,
        **depends,
    ):
        if cea_proj is None:
            self._value = pd.Series(0, geometry.index)
        self._value = cea_proj.area / cea_proj.convex_hull.area


# pylint: disable=no-member


class RdsMeanConvexHull(
    DistrictMeanMixin,
    RdsCompactnessAggregate,
    mname=f"mean{MetricsColumns.CONVEXHULL.capitalize()}",
    display=False,
    values=RdsConvexHull,
): ...


class RdsMinConvexHull(
    DistrictMinMixin,
    RdsCompactnessAggregate,
    mname=f"min{MetricsColumns.CONVEXHULL.capitalize()}",
    display=False,
    values=RdsConvexHull,
): ...


class RdsMaxConvexHull(
    DistrictMaxMixin,
    RdsCompactnessAggregate,
    mname=f"max{MetricsColumns.CONVEXHULL.capitalize()}",
    display=False,
    values=RdsConvexHull,
): ...


class RdsAggConvexHull(
    RdsAggScores, score=MetricsColumns.CONVEXHULL, depends=(RdsMeanConvexHull, RdsMinConvexHull, RdsMaxConvexHull)
): ...


class RdsCutEdges(
    RdsMetric[int],
    mname="cutEdges",
    group=tr("Compactness"),
    level=MetricLevel.PLANWIDE,
    triggers=MetricTriggers.ON_UPDATE_GEOMETRY,
):
    def caption(self):
        return tr("Cut Edges")

    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        **depends,
    ):
        with spatialite_connect(plan.geoPackagePath) as db:
            # select count of unit pairs where
            #   1) assigned districts are different (also takes care of excluding unassigned units from count),
            #   2) combination is unique (count a,b but not b,a),
            #   3) bounding boxes touch or overlap (using spatial index to minimize more intensive adjacency checks)
            #   4) units are adjacent at more than a point
            sql = f"""SELECT count(*)
                FROM assignments a JOIN assignments b
                ON b.{quote_identifier(plan.distField)} != a.{quote_identifier(plan.distField)} AND
                   b.{quote_identifier(plan.geoIdField)} > a.{quote_identifier(plan.geoIdField)}
                AND b.fid IN (
                    SELECT id FROM rtree_assignments_geometry r
                    WHERE r.minx <= st_maxx(a.geometry) and r.maxx >= st_minx(a.geometry)
                    AND r.miny <= st_maxy(a.geometry) and r.maxy >= st_miny(a.geometry)
                )
                AND st_relate(a.geometry, b.geometry, 'F***1****')"""  # noqa: S608

            c = db.execute(sql)
            self._value = c.fetchone()[0]

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        return f"{self._value:,}"


# pylint: disable=abstract-method


class RdsBoolMetric(RdsMetric[bool], mname="__boolmetric"):
    def format(self, idx=None):
        if self._value is None:
            return None

        return tr("YES") if self._value else "NO"

    def forgroundColor(self, idx=None) -> QColor:
        return QColor(Qt.GlobalColor.green) if self._value else QColor(Qt.GlobalColor.red)


# pylint: enable=abstract-method


class RdsContiguityMetric(RdsBoolMetric, mname="contiguity", triggers=MetricTriggers.ON_UPDATE_GEOMETRY):
    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        **depends,
    ):
        if plan is None or len(geometry) == 1:
            self._value = None
            return

        # bool cast ensures the value is not np.True_ or np.False_, which are
        # not json serializable with the standard lib json.dumps function
        self._value = bool(geometry[geometry.index != 0].count_geometries().sum() == plan.allocatedDistricts)

    def tooltip(self, idx=None):
        if self._value:
            return None

        return tr("Plan contains non-contiguous districts\nDouble-click or press enter for details")


class RdsCompleteMetric(RdsBoolMetric, mname="complete", triggers=MetricTriggers.ON_UPDATE_GEOMETRY):
    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        **depends,
    ):
        if plan is None:
            self._value = False
        else:
            self._value = (
                populationData[populationData[plan.distField] == 0].empty
                and populationData[plan.distField].nunique() == plan.numDistricts
            )

    def tooltip(self, idx=None):
        if self._value:
            return None

        return tr("Plan contains unassigned geography\nDouble-click or press enter for details")


register_metrics([RdsTotalPopulationMetric, RdsDeviationMetric, RdsPctDeviationMetric, RdsPlanDeviationMetric], True)
register_metrics(
    [
        CeaProjMetric,
        RdsPolsbyPopper,
        RdsReock,
        RdsConvexHull,
        RdsCutEdges,
        RdsMeanPolsbyPopper,
        RdsMinPolsbyPopper,
        RdsMaxPolsbyPopper,
        RdsMeanReock,
        RdsMinReock,
        RdsMaxReock,
        RdsMeanConvexHull,
        RdsMinConvexHull,
        RdsMaxConvexHull,
        RdsContiguityMetric,
        RdsCompleteMetric,
        RdsAggPolsbyPopper,
        RdsAggReock,
        RdsAggConvexHull,
    ]
)
