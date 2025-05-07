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
from collections.abc import Iterable, Mapping
from copy import copy
from enum import Enum, IntFlag, auto
from numbers import Integral, Real
from types import GenericAlias
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar, Union, _GenericAlias, get_args, get_origin, overload

import geopandas as gpd
import pandas as pd
from qgis.core import QgsField, QgsVectorLayer
from qgis.PyQt.QtCore import QMetaType, QObject, pyqtSignal
from qgis.PyQt.QtGui import QColor

from ..utils import camel_to_kebab, camel_to_snake, kebab_to_camel, tr
from .base.lists import KeyedList
from .base.model import RdsBaseModel, rds_property
from .base.serialization import deserialize_value, serialize_value

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

    def __key__(self) -> str:
        return self._name

    @classmethod
    def get_type(cls) -> type:
        return cls._type

    @abstractmethod
    def calculate(self, populationData: pd.DataFrame, geometry: gpd.GeoSeries, plan: "RdsPlan", **depends): ...

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
        self, populationData: pd.DataFrame, geometry: gpd.GeoSeries, plan: "RdsPlan", values: Iterable[Any]
    ) -> Any: ...

    def calculate(self, populationData: pd.DataFrame, geometry: gpd.GeoSeries, plan: "RdsPlan", **depends):
        values = depends.get(self._source_metric.name())

        if values is None:
            self._value = None
            return

        if isinstance(values, Mapping):
            values = values.values()

        self._value = self.aggregate(populationData, geometry, plan, values)

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

    metrics: KeyedList[RdsMetric]

    distLayer: QgsVectorLayer = None
    distField: str = None

    def __pre_init__(self):
        self._metrics = KeyedList[RdsMetric]({k: v() for k, v in base_metrics.items()})

    @rds_property
    def metrics(self) -> KeyedList[RdsMetric]:
        return self._metrics

    @metrics.serializer
    @staticmethod
    def metrics(value: KeyedList[RdsMetric], memo: dict[int, Any], exclude_none=True):
        metrics = {}
        for name, metric in value.items():
            if metric.serialize() and metric.level() != MetricLevel.DISTRICT:
                metrics[camel_to_kebab(name)] = serialize_value(metric, memo, exclude_none)
            elif not name.startswith("__"):
                metrics[camel_to_kebab(name)] = None

        return metrics

    @metrics.deserializer
    @staticmethod
    def metrics(value: dict[str, dict[str, Any]]):
        metrics: dict[str, RdsMetric] = {}
        for k, v in value.items():
            n = kebab_to_camel(k)
            metric_cls = metrics_classes.get(n)
            if metric_cls is None:
                continue

            if metric_cls.serialize() and metric_cls.level() != MetricLevel.DISTRICT:
                metrics[n] = deserialize_value(metric_cls, v)
            else:
                metrics[n] = metric_cls()

        # instantiate missing metrics that depend on serialized metrics
        need_calc = {}
        for n, metric_cls in metrics_classes.items():
            if n in metrics or metric_cls.level() == MetricLevel.DISTRICT:
                continue

            for m in metrics:
                if metrics_classes[m] in metric_cls.depends():
                    need_calc[n] = metric_cls()
                    break

        batches = get_batches(need_calc, metrics)
        for b in batches:
            for metric in b:
                depends = {m.name(): metrics[m.name()].value for m in metric.depends() if m.name() in metrics}
                metric.calculate(None, None, None, **depends)
                metrics[metric.name()] = metric

        # instantiate the rest
        metrics.update({n: metric_cls() for n, metric_cls in metrics_classes.items() if n not in metrics})

        # sort
        metrics = {n: metrics[n] for n in metrics_classes if n in metrics}

        return KeyedList[RdsMetric](metrics)

    @metrics.setter
    def metrics(self, value: Iterable[RdsMetric]):
        self._metrics.update(value)  # pylint: disable=no-member

    @overload
    def __init__(self, *, parent: Optional[QObject] = None, **kwargs): ...

    @overload
    def __init__(self, metrics: KeyedList[RdsMetric], parent: Optional[QObject] = None): ...

    def __init__(self, metrics: KeyedList[RdsMetric] = None, parent: Optional[QObject] = None, **kwargs):
        # pylint: disable=unsupported-membership-test, unsupported-assignment-operation
        # TODO: limit to metrics selected for plan
        m = KeyedList[RdsMetric]({k: v() for k, v in metrics_classes.items()})
        if metrics is not None:
            m.update(metrics)  # pylint: disable=no-member
        else:
            for k, v in kwargs.items():
                if k in m:
                    m[k] = metrics_classes[k](v)

        super().__init__(m, parent=parent)

    def __getitem__(self, name: str) -> RdsMetric:
        # pylint: disable=unsupported-membership-test, unsubscriptable-object
        if name in self.metrics:
            return self.metrics[name]

        raise KeyError(f"Metric '{name}' not found.")

    def __getattr__(self, name: str) -> Any:
        # pylint: disable=no-member, unsubscriptable-object
        if name in self.metrics.keys():
            return self.metrics[name].value

        return super().__getattr__(name)

    def _get_batches_for_trigger(self, trigger: MetricTriggers):
        # pylint: disable=no-member
        metrics = {name: metric for name, metric in self.metrics.items() if metric.triggers() & trigger}
        ready = {m.name(): m for metric in metrics.values() for m in metric.depends() if not m.triggers() & trigger}

        return get_batches(metrics, ready)

    def updateMetrics(
        self, trigger: MetricTriggers, populationData: pd.DataFrame, geometry: gpd.GeoSeries, plan: "RdsPlan"
    ):
        """called in background thread to recalculate metrics"""
        batches = self._get_batches_for_trigger(trigger)

        for b in batches:
            for metric in b:
                if trigger & metric.triggers():
                    depends = {
                        m.name(): self.metrics[m.name()].value  # pylint: disable=unsubscriptable-object
                        for m in metric.depends()
                        if m.name() in self.metrics  # pylint: disable=unsupported-membership-test
                    }
                    metric.calculate(populationData, geometry, plan, **depends)

    def addDistrictMetricField(self, plan: "RdsPlan", metric: RdsMetric):
        """adds a district metric field to the metrics list"""
        if metric.level() != MetricLevel.DISTRICT:
            raise ValueError("Only district level metrics can be added as fields.")

        if not metric.serialize():
            return

        if metric.get_type() is None:
            return

        if metric.get_type() in (str, bytes):
            t = QMetaType.Type.QString
        elif issubclass(metric.get_type(), Integral):
            t = QMetaType.Type.Int
        elif issubclass(metric.get_type(), Real):
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

    def updateDistrictMetrics(self, trigger: MetricTriggers, plan: "RdsPlan"):
        """updates the district-level metrics in the plan's district layer"""

        def to_dict(value: Union[Mapping, pd.Series, pd.DataFrame]) -> dict:
            if isinstance(value, pd.Series):
                return value.to_dict()
            if isinstance(value, pd.DataFrame):
                return value.to_dict(orient="records")
            if isinstance(value, Mapping):
                return value

            raise TypeError("Unsupported type for serialization.")

        provider = plan.distLayer.dataProvider() if plan.distLayer else None
        if provider is None:
            raise RuntimeError("No district layer available to add the metric field.")

        dist_metrics: dict[str, Union[Mapping, pd.Series, pd.DataFrame]] = {
            provider.fieldNameIndex(camel_to_snake(n)): to_dict(m.value)
            for n, m in self.metrics.items()  # pylint: disable=no-member
            if m.level() == MetricLevel.DISTRICT  # only update district level metrics
            and m.serialize()  # only update metrics that are meant to be serialized
            and m.triggers() & trigger  # only update if the metric is triggered
            and m.value is not None  # only update if the metric has a value
            # only update if the metric has a corresponding field in the district layer
            and provider.fieldNameIndex(camel_to_snake(n)) != -1
        }

        try:
            provider.changeAttributeValues(
                {
                    f.id(): {name: values.get(f[plan.distField]) for name, values in dist_metrics.items()}
                    for f in provider.getFeatures()
                }
            )  # reset the attributes

            plan.distLayer.reload()
        except Exception as e:  # pylint: disable=broad-except
            raise RuntimeError(f"Failed to update district metrics: {e}") from e

    def updateFinished(self, trigger, plan: "RdsPlan"):
        """called in main thread to allow updating UI and emiting signals on main-thread objects"""
        self.metricsAboutToChange.emit()
        batches = self._get_batches_for_trigger(trigger)
        update_districts = False
        for b in batches:
            for metric in b:
                if metric.level() == MetricLevel.DISTRICT:
                    update_districts = True
                metric.finished(plan)

        if update_districts:
            self.updateDistrictMetrics(trigger, plan)

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
