"""QGIS Redistricting Plugin - modular metrics base classes

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
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from copy import copy
from enum import Enum, IntFlag, auto
from numbers import Integral, Real
from types import GenericAlias
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Optional,
    TypeVar,
    Union,
    _GenericAlias,  # type: ignore
    get_args,
    get_origin,
)

import geopandas as gpd
import pandas as pd
from qgis.core import QgsField, QgsVectorLayer
from qgis.PyQt.QtCore import QMetaType, pyqtSignal
from qgis.PyQt.QtGui import QColor

from ..utils import camel_to_kebab, kebab_to_camel, tr
from .base import Property, RdsBaseModel, rds_property
from .lists import KeyedList
from .serialization import deserialize_value, serialize_value

if TYPE_CHECKING:
    from .plan import RdsPlan


class MetricTriggers(IntFlag):
    ON_CREATE_PLAN = auto()
    ON_UPDATE_DEMOGRAPHICS = auto()
    ON_UPDATE_GEOMETRY = auto()
    ON_UPDATE_DISTRICTS = auto()
    ON_UPDATE_GEOFIELDS = auto()


class MetricLevel(Enum):
    PLANWIDE = auto()
    GEOGRAPHIC = auto()
    DISTRICT = auto()


T = TypeVar("T")


class RdsMetric(Generic[T], RdsBaseModel):
    value: T = rds_property(private=True, readonly=True, default=None)

    def __pre_init__(self):
        self._value: T = None

    def __init_subclass__(  # noqa: PLR0913
        cls,
        *args,
        mname: str,
        display: bool = True,
        group: Optional[str] = None,
        level: MetricLevel = MetricLevel.PLANWIDE,
        triggers: MetricTriggers = MetricTriggers.ON_CREATE_PLAN
        | MetricTriggers.ON_UPDATE_DEMOGRAPHICS
        | MetricTriggers.ON_UPDATE_GEOMETRY,
        serialize: bool = True,
        depends: Iterable[type["RdsMetric"]] = None,
        field_type: type = None,
        **kwargs,
    ):
        super().__init_subclass__(*args, **kwargs)
        cls._type = get_args(cls.__orig_bases__[0])[0]  # pylint: disable=no-member
        if cls._type is T:
            cls._type = Any

        if cls.value.type != cls._type:
            cls.__annotations__["value"] = cls._type
            cls.value = copy(cls.value)
            if isinstance(cls._type, (_GenericAlias, GenericAlias)):
                cls.value.type = get_origin(cls._type)
            else:
                cls.value.type = cls._type
            cls.__fields__["value"] = cls.value

        cls._name = mname
        cls._display = display
        cls._group = group
        cls._level = level
        cls._triggers = triggers
        cls._serialize = serialize
        cls._depends: tuple[type["RdsMetric"]] = tuple(depends) if depends else ()
        cls._field_type = field_type if field_type is not None else cls._type

    def __key__(self) -> str:
        return self._name

    @classmethod
    def get_type(cls) -> type:
        return cls._type

    @classmethod
    def field_type(cls) -> type:
        """Get the type for the table field for this metric"""
        return cls._field_type

    @abstractmethod
    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        **depends,
    ): ...

    def finished(self, plan: "RdsPlan"):  # pylint: disable=unused-argument
        ...

    @classmethod
    def name(cls) -> str:
        return cls._name

    @classmethod
    def display(cls) -> bool:
        return cls._display

    @classmethod
    def serialize(cls) -> bool:
        return cls._serialize

    @classmethod
    def triggers(cls) -> MetricTriggers:
        return cls._triggers

    @classmethod
    def level(cls) -> MetricLevel:
        return cls._level

    @classmethod
    def depends(cls) -> Iterable[type["RdsMetric"]]:
        return cls._depends

    def group(self) -> str:
        return self._group

    def caption(self) -> str:
        return tr(self.name().replace("_", " ").title())

    def format(self, idx=None) -> str:
        try:
            if idx is not None:
                return str(self.value[idx])

            return str(self.value)
        except:  # noqa # pylint: disable=bare-except
            return ""

    def forgroundColor(self, idx=None) -> QColor:  # pylint: disable=unused-argument
        return None

    def backgroundColor(self, idx=None) -> QColor:  # pylint: disable=unused-argument
        return None

    def tooltip(self, idx=None) -> str:  # pylint: disable=unused-argument
        return None


class RdsAggregateMetric(RdsMetric[T], mname="__aggregate"):
    def __init_subclass__(cls, *args, mname: str, level=MetricLevel.PLANWIDE, values: type[RdsMetric], **kwargs):
        super().__init_subclass__(*args, mname=mname, level=level, **kwargs)
        cls._source_metric = values

    @classmethod
    def source_metric(cls) -> type[RdsMetric]:
        return cls._source_metric

    @classmethod
    def depends(cls):
        dependencies = super().depends()
        if cls._source_metric is None or cls._source_metric in dependencies:
            return dependencies

        return (cls._source_metric, *dependencies)

    @abstractmethod
    def aggregate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        values: Iterable[Any],
    ) -> Any: ...

    def calculate(
        self,
        populationData: pd.DataFrame,
        districtData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        plan: "RdsPlan",
        **depends,
    ):
        values = depends.get(self._source_metric.name())

        if values is None:
            self._value = None
            return

        if isinstance(values, Mapping):
            values = values.values()

        self._value = self.aggregate(populationData, districtData, geometry, plan, values)

    @classmethod
    def short_name(cls):
        return tr("Aggregate")


metrics_classes: dict[str, type[RdsMetric]] = {}
base_metrics: dict[str, type[RdsMetric]] = {}
aggregates: dict[str, list[RdsAggregateMetric]] = defaultdict(default_factory=list)


def register_metrics(classes: Union[type[RdsMetric], Iterable[type[RdsMetric]]], base: bool = False):
    if not isinstance(classes, Iterable):
        classes: list[type[RdsMetric]] = [classes]

    for metric in classes:
        metrics_classes[metric.name()] = metric
        if base:
            base_metrics[metric.name()] = metric

        if isinstance(metric, RdsAggregateMetric) and metric.source_metric() is not None:
            aggregates[metric.source_metric().name()].append(metric)


def supported_aggregates(metric: RdsMetric) -> Iterable[RdsAggregateMetric]:
    return aggregates[metric.name()]


def _format_dependencies(name_to_deps: dict[str, set[str]]):
    msg = []
    for name, deps in name_to_deps.items():
        for parent in deps:
            msg.append(f"{name} -> {parent}")
    return "\n".join(msg)


def get_batches(metrics: Mapping[str, RdsMetric], ready: dict[str, RdsMetric] = None):
    if ready is None:
        ready = {}

    name_to_deps = {name: {m.name() for m in metric.depends()} for name, metric in metrics.items()}

    # remove the dependencies that have already been calculated
    if ready:
        for depends in name_to_deps.values():
            depends.difference_update(ready)

    batches: list[tuple[RdsMetric, ...]] = []
    while name_to_deps:
        ready = {name for name, deps in name_to_deps.items() if not deps}
        if not ready:
            msg = f"Circular dependencies found!\n{_format_dependencies(name_to_deps)}"
            raise ValueError(msg)

        for name in ready:
            del name_to_deps[name]

        for depends in name_to_deps.values():
            depends.difference_update(ready)

        batches.append([metrics[name] for name in ready])

    return batches


class RdsMetrics(RdsBaseModel):
    metricsAboutToChange = pyqtSignal()
    metricsChanged = pyqtSignal()

    metrics: KeyedList[str, RdsMetric]

    distLayer: QgsVectorLayer = None
    distField: str = None

    def __pre_init__(self):
        self._metrics = KeyedList([v() for v in base_metrics.values()], elem_type=RdsMetric)

    @Property
    def metrics(self) -> KeyedList[str, RdsMetric]:
        return self._metrics

    @metrics.serializer
    @staticmethod
    def metrics(value: KeyedList[str, RdsMetric], memo: dict[int, Any], exclude_none=True):
        metrics = {}
        for name, metric in value.items():
            if name.startswith("__"):  # shouldn't happen, but just in case
                continue

            if metric.serialize() and metric.level() != MetricLevel.DISTRICT:
                metrics[camel_to_kebab(name)] = serialize_value(metric, memo, exclude_none)
            else:
                metrics[camel_to_kebab(name)] = None

        return metrics

    @metrics.deserializer
    @staticmethod
    def metrics(value: dict[str, dict[str, Any]]):
        metrics: dict[str, RdsMetric] = {}
        ready: dict[str, RdsMetric] = {}
        for k, v in value.items():
            n = kebab_to_camel(k)
            metric_cls = metrics_classes.get(n)
            if metric_cls is None:
                continue

            if v is None or not metric_cls.serialize() or metric_cls.level() == MetricLevel.DISTRICT:
                metrics[n] = metric_cls()
            else:
                metrics[n] = deserialize_value(metric_cls, v)
                ready[n] = metrics[n]

        # instantiate missing metrics that depend on serialized metrics
        need_calc = {}
        for n, metric in metrics.items():
            if n in ready or metric.level() == MetricLevel.DISTRICT:
                continue

            for m in metrics:
                if metrics_classes[m] in metric.depends():
                    need_calc[n] = metric
                    break

        batches = get_batches(need_calc, ready)
        for b in batches:
            for metric in b:
                depends = {m.name(): metrics[m.name()].value for m in metric.depends() if m.name() in metrics}
                metric.calculate(None, None, None, None, **depends)

        # sort
        metrics = {n: metrics[n] for n in metrics_classes if n in metrics}

        return KeyedList(metrics.values(), elem_type=RdsMetric)

    @metrics.setter
    def metrics(self, value: Iterable[RdsMetric]):
        self._metrics.clear()
        self._metrics.extend(value)  # pylint: disable=no-member

    def __getitem__(self, name: str) -> RdsMetric:
        if (m := self.metrics.get(name, None)) is not None:
            return m

        raise KeyError(f"Metric '{name}' not found.")

    def __getattr__(self, name: str) -> Any:
        if (m := self.metrics.get(name, None)) is not None:
            return m.value

        return super().__getattr__(name)

    def __iter__(self) -> Iterator[RdsMetric]:
        yield from self.metrics

    def addDistrictMetricField(self, plan: "RdsPlan", metric: RdsMetric):
        """adds a district metric field to the metrics list"""
        if metric.level() != MetricLevel.DISTRICT:
            raise ValueError("Only district level metrics can be added as fields.")

        if not metric.serialize() or metric.field_type() is None:
            return

        if metric.field_type() in (str, bytes):
            t = QMetaType.Type.QString
        elif issubclass(metric.field_type(), Integral):
            t = QMetaType.Type.Int
        elif issubclass(metric.field_type(), Real):
            t = QMetaType.Type.Double
        else:
            return

        provider = plan.distLayer.dataProvider() if plan.distLayer else None
        if provider is None:
            raise RuntimeError("No district layer available to add the metric field.")

        if provider.fieldNameIndex(metric.name()) != -1:
            # field already exists
            return

        field = QgsField(metric.name(), t)
        if provider.addAttributes([field]):
            plan.distLayer.updateFields()

    def beginUpdate(self):
        """called before updating metrics to allow for any pre-update actions"""
        self.metricsAboutToChange.emit()

    def endUpdate(self):
        """called after updating metrics to allow for any post-update actions"""
        self.metricsChanged.emit()

    def addMetric(self, metric_cls: type[RdsMetric]):
        """adds a metric to the metrics list"""
        if not issubclass(metric_cls, RdsMetric):
            raise TypeError("Only RdsMetric subclasses can be added.")

        if metric_cls.name() in self.metrics:  # pylint: disable=unsupported-membership-test
            raise ValueError(f"Metric '{metric_cls.name()}' already exists.")

        for dep in metric_cls.depends():
            if dep.name() not in self.metrics:  # pylint: disable=unsupported-membership-test
                self.addMetric(dep)

        metric = metric_cls()
        self.metrics.append(metric)  # pylint: disable=no-member

        return metric_cls

    def removeMetric(self, metric_cls: type[RdsMetric]):
        """removes a metric from the metrics list"""
        if not issubclass(metric_cls, RdsMetric):
            raise TypeError("Only RdsMetric subclasses can be removed.")

        if metric_cls.name() not in self.metrics:  # pylint: disable=unsupported-membership-test
            raise ValueError(f"Metric '{metric_cls.name()}' does not exist.")

        metric = self.metrics[metric_cls.name()]  # pylint: disable=unsubscriptable-object
        self.metrics.remove(metric)  # pylint: disable=no-member

        # TODO: handle removing the metric field from the district layer if it exists
        # TODO: handle removing metrics that are dependencies of the removed metric and are no longer needed
