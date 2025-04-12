from abc import (
    ABC,
    abstractmethod
)
from collections import defaultdict
from collections.abc import Iterable
from enum import (
    Enum,
    IntFlag,
    auto
)
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Mapping,
    Optional,
    TypeVar,
    Union,
    get_args,
    overload
)

import geopandas as gpd
import pandas as pd
from qgis.core import QgsField
from qgis.PyQt.QtCore import (
    QObject,
    QVariant,
    pyqtSignal
)
from qgis.PyQt.QtGui import QColor

from ..utils import tr
from .base.lists import KeyedList
from .base.model import RdsBaseModel
from .base.serialization import (
    camel_to_snake,
    deserialize_value,
    kebab_to_camel,
    register_serializer,
    serialize_value
)
from .field import RdsGeoField

if TYPE_CHECKING:
    from . import RdsPlan


class MetricTriggers(IntFlag):
    ON_CREATE_PLAN = auto()
    ON_UPDATE_DEMOGRAPHICS = auto()
    ON_UPDATE_GEOMETRY = auto()


class MetricLevel(Enum):
    PLANWIDE = auto()
    GEOGRAPHIC = auto()
    DISTRICT = auto()


T = TypeVar("T")


class RdsMetric(Generic[T], ABC):
    def __init__(self, plan: 'RdsPlan' = None):
        self._value: T = None
        self.plan = plan

    def __init_subclass__(
        cls,
        *args,
        mname: str,
        display: bool = True,
        group: Optional[str] = None,
        level: MetricLevel = MetricLevel.PLANWIDE,
        triggers: MetricTriggers = ~MetricTriggers(0),  # all triggers
        serialize: bool = True,
        depends: Iterable[type['RdsMetric']] = None,
        **kwargs
    ):
        super().__init_subclass__(*args, **kwargs)
        cls._type = get_args(cls.__orig_bases__[0])[0]  # pylint: disable=no-member
        if cls._type is T:
            cls._type = None

        cls._name = mname
        cls._display = display
        cls._group = group
        cls._level = level
        cls._triggers = triggers
        cls._serialize = serialize
        cls._depends: tuple[type['RdsMetric']] = tuple(depends) if depends else ()

    @property
    def plan(self):
        return self._plan

    @plan.setter
    def plan(self, value: 'RdsPlan'):
        self._plan = value

    @classmethod
    def get_type(cls) -> type:
        return cls._type

    @abstractmethod
    def calculate(
        self,
        populationData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        **depends
    ):
        ...

    def finished(self):
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
    def depends(cls) -> Iterable[type['RdsMetric']]:
        return cls._depends

    def group(self) -> str:
        return self._group

    def caption(self) -> str:
        return tr(self.name().replace("_", " ").title())

    def value(self) -> T:
        return self._value

    def setValue(self, value: T):
        self._value = value

    def format(self, idx=None) -> str:
        try:
            if idx is not None:
                return str(self._value[idx])

            return str(self._value)
        except:  # pylint: disable=bare-except
            return ""

    def color(self, idx=None) -> QColor:  # pylint: disable=unused-argument
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
        geometry: gpd.GeoSeries,
        values: Iterable[Any]
    ) -> Any:
        ...

    def calculate(
        self,
        populationData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        **depends
    ):
        values = depends.get(self._source_metric.name())

        if values is None:
            self._value = None
            return

        if isinstance(values, Mapping):
            values = values.values()

        self._value = self.aggregate(populationData, geometry, values)

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

    name_to_deps = {name: set(m.name() for m in metric.depends()) for name, metric in metrics.items()}

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

    metrics: KeyedList[RdsMetric] = None

    @property
    def plan(self):
        return self._plan

    @plan.setter
    def plan(self, value: 'RdsPlan'):
        self._plan = value
        for m in self.metrics:  # pylint: disable=not-an-iterable
            m.plan = value

    @overload
    def __init__(self, plan: 'RdsPlan'):
        ...

    @overload
    def __init__(self, metrics: Iterable[RdsMetric]):
        ...

    def __init__(self, metrics, parent: Optional[QObject] = None):
        if metrics is None or isinstance(metrics, KeyedList):
            self._plan = None
        else:
            self._plan = metrics
            metrics = None

        # TODO: limit to metrics selected for plan
        m = KeyedList({k: v(self._plan) for k, v in metrics_classes.items()})
        if metrics is not None:
            m.update(metrics)

        super().__init__(m, parent=parent)

    def __pre_init__(self):
        self._plan: 'RdsPlan' = None

    def __getattr__(self, name: str) -> Any:
        # pylint: disable=no-member, unsubscriptable-object
        if name in self.metrics.keys():
            return self.metrics[name].value()

        return super().__getattr__(name)

    def _get_batches_for_trigger(self, trigger: MetricTriggers):
        metrics = {name: metric for name, metric in self.metrics.items() if metric.triggers() & trigger}
        ready = {m.name(): m for metric in metrics.values() for m in metric.depends() if not m.triggers() & trigger}

        return get_batches(metrics, ready)

    def updateMetrics(
        self,
        trigger: MetricTriggers,
        populationData: pd.DataFrame,
        geometry: gpd.GeoSeries
    ):
        """called in background thread to recalculate metrics"""
        batches = self._get_batches_for_trigger(trigger)

        for b in batches:
            for metric in b:
                if trigger & metric.triggers():

                    depends = {
                        m.name(): self.metrics[m.name()].value()  # pylint: disable=unsubscriptable-object
                        for m in metric.depends()
                        if m.name() in self.metrics  # pylint: disable=unsupported-membership-test
                    }
                    metric.calculate(populationData, geometry, **depends)

    def addDistrictMetricField(self, metric: RdsMetric):
        """adds a district metric field to the metrics list"""
        if metric.level() != MetricLevel.DISTRICT:
            raise ValueError("Only district level metrics can be added as fields.")

        if not metric.serialize():
            return

        if metric.get_type() is None:
            return

        if metric.get_type() == float:
            t = QVariant.Double
        elif metric.get_type() == int:
            t = QVariant.Int
        elif metric.get_type() == str:
            t = QVariant.String
        else:
            return

        provider = self.plan.distLayer.dataProvider() if self.plan and self.plan.distLayer else None
        if provider is None:
            raise RuntimeError("No district layer available to add the metric field.")

        if provider.fieldNameIndex(metric.name()) != -1:
            # field already exists
            return

        field = QgsField(metric.name(), t)
        if provider.addAttributes([field]):
            self.plan.distLayer.updateFields()

    def updateDistrictMetrics(self, trigger: MetricTriggers):
        """updates the district-level metrics in the plan's district layer"""
        def to_dict(value: Union[Mapping, pd.Series, pd.DataFrame]) -> dict:
            if isinstance(value, pd.Series):
                return value.to_dict()
            if isinstance(value, pd.DataFrame):
                return value.to_dict(orient='records')
            if isinstance(value, Mapping):
                return value

            raise TypeError("Unsupported type for serialization.")

        provider = self.plan.distLayer.dataProvider() if self.plan and self.plan.distLayer else None
        if provider is None:
            raise RuntimeError("No district layer available to add the metric field.")

        dist_metrics: dict[str, Union[Mapping, pd.Series, pd.DataFrame]] = {
            provider.fieldNameIndex(camel_to_snake(n)): to_dict(m.value())
            for n, m in self.metrics.items()
            if m.level() == MetricLevel.DISTRICT  # only update district level metrics
            and m.serialize()  # only update metrics that are meant to be serialized
            and m.triggers() & trigger  # only update if the metric is triggered
            and m.value() is not None  # only update if the metric has a value
            # only update if the metric has a corresponding field in the district layer
            and provider.fieldNameIndex(camel_to_snake(n)) != -1
        }

        try:
            provider.changeAttributeValues({
                f.id(): {name: values.get(f[self.plan.distField]) for name, values in dist_metrics.items()}
                for f in provider.getFeatures()
            })  # reset the attributes

            self.plan.distLayer.reload()
        except Exception as e:  # pylint: disable=broad-except
            raise RuntimeError(f"Failed to update district metrics: {e}") from e

    def updateFinished(self, trigger):
        """called in main thread to allow updating UI and emiting signals on main-thread objects"""
        self.metricsAboutToChange.emit()
        batches = self._get_batches_for_trigger(trigger)

        for b in batches:
            for metric in b:
                metric.finished()

        self.updateDistrictMetrics(trigger)

        self.metricsChanged.emit()

    def updateGeoFields(self, geoFields: Iterable[RdsGeoField]):
        for metric in self.metrics:  # pylint: disable=not-an-iterable
            if metric.level() == MetricLevel.GEOGRAPHIC:
                if hasattr(metric, "updateGeoFields"):
                    metric.updateGeoFields(geoFields)


def serialize_metrics(value: RdsMetrics, memo: dict[int, Any], exclude_none=True):
    data = {}
    for name, metric in value.metrics.items():
        if metric.serialize() and metric.level() != MetricLevel.DISTRICT:
            v = metric.value()
            if v is not None or not exclude_none:
                data[name] = serialize_value(metric.value(), memo, exclude_none)

    return {'metrics': data}


def deserialize_metrics(cls: type[RdsMetrics], value: dict[str, dict[str, Any]]):
    metrics_data = value.get('metrics', {})
    metrics: dict[str, RdsMetric] = {}
    for k, v in metrics_data.items():
        n = kebab_to_camel(k)
        metric_cls = metrics_classes.get(n)
        if metric_cls is None:
            continue

        metric = metric_cls()
        metric.setValue(deserialize_value(metric.get_type(), v))
        metrics[n] = metric

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
            depends = {
                m.name(): metrics[m.name()].value()
                for m in metric.depends()
                if m.name() in metrics
            }
            metric.calculate(None, None, **depends)
            metrics[metric.name()] = metric

    # instantiate the rest
    metrics.update(
        {n: metric_cls() for n, metric_cls in metrics_classes.items() if n not in metrics}
    )

    # sort
    metrics = {n: metrics[n] for n in metrics_classes if n in metrics}

    return cls(KeyedList(metrics))


register_serializer(RdsMetrics, serialize_metrics, deserialize_metrics)
