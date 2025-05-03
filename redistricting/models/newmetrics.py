from abc import abstractmethod
from collections import defaultdict
from collections.abc import (
    Callable,
    Iterable,
    Mapping
)
from enum import (
    Enum,
    IntFlag,
    auto
)
from typing import (
    Any,
    Generic,
    Optional,
    TypeVar,
    Union,
    get_args
)

import geopandas as gpd
import pandas as pd
from qgis.core import (
    QgsField,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QMetaType,
    pyqtSignal
)
from qgis.PyQt.QtGui import QColor

from ..utils import tr
from .base.lists import KeyedList
from .base.model import (
    InitVar,
    RdsBaseModel,
    fields,
    rds_property
)
from .base.serialization import (
    camel_to_kebab,
    camel_to_snake,
    deserialize_value,
    kebab_to_camel,
    register_serializer,
    serialize_value
)


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


_T = TypeVar("_T")


class RdsMetric(Generic[_T], RdsBaseModel):
    value: Any = rds_property(private = True, readonly=True, default=None)

    def __init_subclass__(
        cls,
        *args,
        mname: str,
        display: bool = True,
        group: Optional[str] = None,
        level: MetricLevel = MetricLevel.PLANWIDE,
        triggers: MetricTriggers = MetricTriggers.ON_CREATE_PLAN | MetricTriggers.ON_UPDATE_DEMOGRAPHICS | MetricTriggers.ON_UPDATE_GEOMETRY,
        serialize: bool = True,
        depends: Iterable[type['RdsMetric']] = None,
        **kwargs
    ):
        super().__init_subclass__(*args, **kwargs)
        cls._type = get_args(cls.__orig_bases__[0])[0]  # pylint: disable=no-member
        if cls._type is _T:
            cls._type = None
        else:
            cls.__annotations__['value'] = cls._type
            fields(cls)[0].type = cls._type

        if level == MetricLevel.DISTRICT:
            triggers |= MetricTriggers.ON_UPDATE_DISTRICTS
            depends = tuple(depends) if depends else ()
            if RdsDistrictsMetric not in depends:
                depends = (RdsDistrictsMetric, *depends)
        elif level == MetricLevel.GEOGRAPHIC:
            triggers |= MetricTriggers.ON_UPDATE_GEOFIELDS
            depends = tuple(depends) if depends else ()
            if RdsGeoFieldsMetric not in depends:
                depends = (RdsGeoFieldsMetric, *depends)

        cls._name = mname
        cls._display = display
        cls._group = group
        cls._level = level
        cls._triggers = triggers
        cls._serialize = serialize
        cls._depends: tuple[type['RdsMetric']] = tuple(depends) if depends else ()

    def name(self):
        return self._name
    
    @classmethod
    def level(cls):
        return cls._level
    
    @classmethod
    def group(cls):
        return cls._group
    
    @classmethod
    def triggers(cls):
        return cls._triggers
    
    @classmethod
    def display(cls):
        return cls._display
    
    @classmethod
    def serialize(cls):
        return cls._serialize

    @classmethod
    def depends(cls):
        return cls._depends
    
    @classmethod
    def get_type(cls) -> type:
        return cls._type

    def __key__(self) -> str:
        return type(self)._name
    
    @abstractmethod
    def calculate(
        self,
        triggers: MetricTriggers,
        populationData: pd.DataFrame,
        geometry: gpd.GeoSeries,
        **depends
    ):
        ...

    def finished(self, triggers: MetricTriggers):
        ...

    def caption(self) -> str:
        return self._name.replace("_", " ").title()

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
    
class RdsPropertyGetterMetric(RdsMetric, mname="__getter", serialize=False):
    instance: InitVar[Any] = None
    prop_name: InitVar[str] = None

    def name(self):
        return self._prop
    
    def __post_init__(self, instance: Any, prop_name: str):
        self._instance = instance
        self._prop = prop_name

    def calculate(self, triggers, populationData, geometry, **depends):
        self._value = getattr(self._instance, self._prop)
    
    
class RdsDistrictsMetric(RdsMetric[Iterable[int]], mname="__districts", triggers=MetricTriggers.ON_UPDATE_DISTRICTS, serialize=False):
    distField: str = 'district'

    def calculate(self, populationData: pd.DataFrame, geometry, **depends):
        self._value = list(populationData[self.distField].unique())

class RdsGeoFieldsMetric(RdsMetric[Iterable[str]], mname="__geofields", triggers=MetricTriggers.ON_UPDATE_GEOFIELDS, serialize=False):
    geoFields: list[str] = rds_property(private="_value", serialize=False)
    
    def calculate(self, populationData: pd.DataFrame, geometry, **depends):
        ...

class RdsAggregateMetric(RdsMetric[_T], mname="__aggregate"):
    def __init_subclass__(cls, *args, mname: str, values: type[RdsMetric], level=MetricLevel.PLANWIDE, **kwargs):
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

        self._value = self.aggregate(populationData, geometry,values)

    @classmethod
    def short_name(cls):
        return tr("Aggregate")
    
metrics_classes: dict[str, type[RdsMetric]] = {
    RdsDistrictsMetric.name(): RdsDistrictsMetric, 
    RdsGeoFieldsMetric.name(): RdsGeoFieldsMetric
}
base_metrics: dict[str, type[RdsMetric]] = {
    RdsDistrictsMetric.name(): RdsDistrictsMetric, 
    RdsGeoFieldsMetric.name(): RdsGeoFieldsMetric
}
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
    def serialize_metrics(value: KeyedList[RdsMetric], memo: dict[int, Any], exclude_none=True):
        metrics = {}
        for name, metric in value.items():
            if metric.serialize() and metric.level() != MetricLevel.DISTRICT:
                metrics[camel_to_kebab(name)] = serialize_value(metric, memo, exclude_none)
            elif not name.startswith("__"):
                metrics[camel_to_kebab(name)] = None

        return metrics


    @metrics.deserializer
    @staticmethod
    def deserialize_metrics(value: dict[str, dict[str, Any]]):
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
                depends = {
                    m.name(): metrics[m.name()].value
                    for m in metric.depends()
                    if m.name() in metrics
                }
                metric.calculate(None, None, None, **depends)
                metrics[metric.name()] = metric

        # instantiate the rest
        metrics.update(
            {n: metric_cls() for n, metric_cls in metrics_classes.items() if n not in metrics}
        )

        # sort
        metrics = {n: metrics[n] for n in metrics_classes if n in metrics}

        return KeyedList[RdsMetric](metrics)

    
    @metrics.setter
    def metrics(self, value: Iterable[RdsMetric]):
        self._metrics.update(value)

    def __getitem__(self, name: str) -> RdsMetric:
        if name in self.metrics:  # pylint: disable=unsupported-membership-test
            return self.metrics[name]  # pylint: disable=unsubscriptable-object

        raise KeyError(f"Metric '{name}' not found.")

    def __getattr__(self, name: str) -> Any:
        # pylint: disable=no-member, unsubscriptable-object
        if name in self.metrics.keys():
            return self.metrics[name].value

        return super().__getattr__(name)
    
    def _has_dependants(self, metric: type[RdsMetric]):
        for m in self.metrics:
            if metric in m.depends():
                return True
            
        return False

    def _get_batches_for_trigger(self, trigger: MetricTriggers):
        metrics = {name: metric for name, metric in self.metrics.items() if metric.triggers() & trigger}
        ready = {m.name(): m for metric in metrics.values() for m in metric.depends() if not m.triggers() & trigger}

        return get_batches(metrics, ready)

    def updateMetrics(
        self,
        trigger: MetricTriggers,
        populationData: pd.DataFrame,
        geometry: gpd.GeoSeries,
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
                    metric.calculate(populationData, geometry, **depends)

    def addDistrictMetricField(self, metric: RdsMetric):
        """adds a district metric field to the metrics list"""
        if metric.level() != MetricLevel.DISTRICT:
            raise ValueError("Only district level metrics can be added as fields.")

        if not metric.serialize():
            return

        if metric.get_type() is None:
            return

        if metric.get_type() is float:
            t = QMetaType.Type.Double
        elif metric.get_type() is int:
            t = QMetaType.Type.Int
        elif metric.get_type() is str:
            t = QMetaType.Type.QString
        else:
            return

        provider = self.distLayer.dataProvider() if self.distLayer else None
        if provider is None:
            raise RuntimeError("No district layer available to add the metric field.")

        if provider.fieldNameIndex(metric.name()) != -1:
            # field already exists
            return

        field = QgsField(metric.name(), t)
        if provider.addAttributes([field]):
            self.distLayer.updateFields()

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

        provider = self.distLayer.dataProvider() if self.distLayer else None
        if provider is None:
            raise RuntimeError("No district layer available to add the metric field.")

        dist_metrics: dict[str, Union[Mapping, pd.Series, pd.DataFrame]] = {
            provider.fieldNameIndex(camel_to_snake(n)): to_dict(m.value)
            for n, m in self.metrics.items()
            if m.level() == MetricLevel.DISTRICT  # only update district level metrics
            and m.serialize()  # only update metrics that are meant to be serialized
            and m.triggers() & trigger  # only update if the metric is triggered
            and m.value is not None  # only update if the metric has a value
            # only update if the metric has a corresponding field in the district layer
            and provider.fieldNameIndex(camel_to_snake(n)) != -1
        }

        try:
            provider.changeAttributeValues({
                f.id(): {name: values.get(f[self.distField]) for name, values in dist_metrics.items()}
                for f in provider.getFeatures()
            })  # reset the attributes

            self.distLayer.reload()
        except Exception as e:  # pylint: disable=broad-except
            raise RuntimeError(f"Failed to update district metrics: {e}") from e

    def updateFinished(self, trigger):
        """called in main thread to allow updating UI and emiting signals on main-thread objects"""
        self.metricsAboutToChange.emit()
        batches = self._get_batches_for_trigger(trigger)
        update_districts = False
        for b in batches:
            for metric in b:
                if metric.level() == MetricLevel.DISTRICT:
                    update_districts = True
                metric.finished(trigger)

        if update_districts:
            self.updateDistrictMetrics(trigger)

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
        self.metrics.append(metric)

        return metric_cls

    def removeMetric(self, metric_cls: type[RdsMetric]):
        """removes a metric from the metrics list"""
        if not issubclass(metric_cls, RdsMetric):
            raise TypeError("Only RdsMetric subclasses can be removed.")

        if metric_cls.name() not in self.metrics:  # pylint: disable=unsupported-membership-test
            raise ValueError(f"Metric '{metric_cls.name()}' does not exist.")

        metric = self.metrics[metric_cls.name()]  # pylint: disable=unsubscriptable-object
        self.metrics.remove(metric)

        # TODO: handle removing the metric field from the district layer if it exists
        # TODO: handle removing metrics that are dependencies of the removed metric and are no longer needed


def serialize_metrics(value: KeyedList[RdsMetric], memo: dict[int, Any], exclude_none=True):
    metrics = {}
    for name, metric in value.items():
        if metric.serialize() and metric.level() != MetricLevel.DISTRICT:
            metrics[camel_to_kebab(name)] = serialize_value(metric, memo, exclude_none)
        elif not name.startswith("__"):
            metrics[camel_to_kebab(name)] = None

    return metrics


def deserialize_metrics(cls: type[RdsMetrics], value: dict[str, dict[str, Any]]):
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
            depends = {
                m.name(): metrics[m.name()].value
                for m in metric.depends()
                if m.name() in metrics
            }
            metric.calculate(None, None, None, **depends)
            metrics[metric.name()] = metric

    # instantiate the rest
    metrics.update(
        {n: metric_cls() for n, metric_cls in metrics_classes.items() if n not in metrics}
    )

    # sort
    metrics = {n: metrics[n] for n in metrics_classes if n in metrics}

    return cls(metrics=KeyedList[RdsMetric](metrics))


register_serializer(RdsMetrics, serialize_metrics, deserialize_metrics)
