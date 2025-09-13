"""QGIS Redistricting Plugin - plan updater

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

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import repeat
from typing import TYPE_CHECKING, Any, Optional, Union

import geopandas as gpd
import pandas as pd
import shapely.ops
from qgis.core import QgsFeatureRequest, QgsFeedback, QgsTask
from qgis.PyQt.QtCore import QObject, QRunnable, QSignalMapper, QThreadPool
from shapely import MultiPolygon, Polygon

from ..models import DistrictColumns, MetricTriggers
from ..utils import spatialite_connect, tr
from ..utils.misc import quote_identifier
from .districtio import DistrictReader
from .metrics import MetricsService
from .updateservice import IncrementalFeedback, UpdateParams, UpdateService

if TYPE_CHECKING:
    from ..models import RdsPlan


class DissolveWorker(QRunnable):
    def __init__(self, dist: int, geoms: Sequence[MultiPolygon], cb=None):
        super().__init__()
        self.dist = dist
        self.geoms = geoms
        self.merged = None
        self.callback = cb

    def run(self):
        self.merged = shapely.ops.unary_union(self.geoms)
        if isinstance(self.merged, Polygon):
            self.merged = MultiPolygon([self.merged])

        if self.callback:
            self.callback()


@dataclass
class DistrictUpdateParams(UpdateParams):
    includeDemographics: bool
    includeGeometry: bool
    updateDistricts: Optional[set[int]] = None
    totalPopulation: Optional[int] = None
    populationData: Optional[pd.DataFrame] = None
    districtData: Optional[Union[pd.DataFrame, gpd.GeoDataFrame]] = None
    geometry: Optional[gpd.GeoSeries] = None


class DistrictUpdater(UpdateService):
    paramsCls = DistrictUpdateParams

    def __init__(self, metricsService: MetricsService, parent: Optional[QObject] = None):
        super().__init__(tr("Calculating district geometry and demographics"), parent)
        self._metricsService = metricsService
        self._updateDistricts: dict["RdsPlan", set[int]] = {}
        self._beforeCommitSignals = QSignalMapper(self)
        self._beforeCommitSignals.mappedObject.connect(self.checkForChangedAssignments)
        self._afterCommitSignals = QSignalMapper(self)
        self._afterCommitSignals.mappedObject.connect(self.startUpdateDistricts)

    def _disolveGeometry(
        self, plan: "RdsPlan", update: gpd.GeoDataFrame, feedback: Optional[IncrementalFeedback] = None
    ):
        def dissolve_progress():
            nonlocal count, total
            count += 1
            feedback.updateProgress(total, count)

        g_geom = update[[plan.distField, "geometry"]].groupby(plan.distField)
        total = len(g_geom) + 1
        count = 0
        geoms: dict[int, shapely.MultiPolygon] = {}
        pool = QThreadPool()
        workers: list[DissolveWorker] = []
        for g, v in g_geom["geometry"]:
            if g == 0:
                geoms[g] = None
                count += 1
                feedback.updateProgress(total, count)
            else:
                worker = DissolveWorker(int(g), v.array, dissolve_progress if feedback is not None else None)
                worker.setAutoDelete(False)
                workers.append(worker)
                pool.start(worker)

        pool.waitForDone()
        geoms |= {t.dist: t.merged for t in workers}
        return geoms

    def _saveDistricts(self, plan: "RdsPlan", params: DistrictUpdateParams, feedback: IncrementalFeedback):
        name = pd.Series(
            [plan.districts.get(d).name if plan.districts.has(d) else str(d) for d in params.districtData.index],
            index=params.districtData.index,
        )
        members = pd.Series(
            [
                0 if d == 0 else plan.districts.get(d).members if plan.districts.has(d) else 1
                for d in params.districtData.index
            ],
            index=params.districtData.index,
            dtype=int,
        )

        params.districtData = params.districtData.join(
            pd.DataFrame({DistrictColumns.NAME: name, DistrictColumns.MEMBERS: members})
        )

        with spatialite_connect(plan.geoPackagePath) as db:
            # Account for districts with no assignments --
            # otherwise, they will never be updated in the database
            if params.updateDistricts is None:
                zero = set(range(0, plan.numDistricts + 1)) - set(params.districtData.index)
            else:
                zero = params.updateDistricts - set(params.districtData.index)

            if zero:
                parameters = ",".join(repeat("?", len(zero)))
                sql = f"DELETE FROM districts WHERE {quote_identifier(plan.distField)} IN ({parameters})"  # noqa: S608
                db.execute(sql, [str(d) for d in zero])
                db.commit()

            # Update existing dictricts
            fields = {
                quote_identifier(f): f"GeomFromText(:{f})" if f == "geometry" else f":{f}"
                for f in list(params.districtData.columns)
            }
            if params.includeGeometry:
                data = (d._asdict() for d in params.districtData.to_wkt().itertuples())
            else:
                data = (d._asdict() for d in params.districtData.itertuples())
            parameters = ",".join(f"{field} = {param}" for field, param in fields.items())
            sql = (
                "UPDATE districts "  # noqa: S608
                f"SET {parameters} "
                f"WHERE {quote_identifier(plan.distField)} = :Index"
            )
            db.executemany(sql, data)
            db.commit()

            fields = {quote_identifier(plan.distField): ":Index"} | fields
            sql = f"INSERT OR IGNORE INTO districts ({','.join(fields.keys())}) VALUES ({','.join(fields.values())})"  # noqa: S608
            db.executemany(sql, data)
            db.commit()
            feedback.updateProgress(1, 1)

    def run(self, task: Optional[QgsTask], plan: "RdsPlan", params: DistrictUpdateParams):
        feedback = IncrementalFeedback(task or QgsFeedback())

        feedback.setProgressIncrement(0, 40)
        params.populationData = self._loadAssignments(
            plan, True, params.includeDemographics, params.includeGeometry, feedback
        )

        if params.includeDemographics:
            params.totalPopulation = int(params.populationData[DistrictColumns.POPULATION].sum())

        pop_cols: list[str] = [
            c for c in params.populationData.columns if not plan.geoFields.has(c) and c != "geometry"
        ]
        params.districtData = params.populationData[pop_cols].groupby(by=plan.distField).sum()

        if params.includeGeometry:
            feedback.setProgressIncrement(40, 90)
            if params.updateDistricts is not None:
                assignments = params.populationData.loc[
                    params.populationData[plan.distField].isin(params.updateDistricts), [plan.distField, "geometry"]
                ]
            else:
                assignments = params.populationData[[plan.distField, "geometry"]]

            geoms = self._disolveGeometry(plan, assignments, feedback)
            params.geometry = gpd.GeoSeries(geoms)
            params.districtData = gpd.GeoDataFrame(
                params.districtData, geometry=params.geometry, crs=params.populationData.crs
            )

        feedback.setProgressIncrement(90, 100)
        self._saveDistricts(plan, params, feedback)

        return params

    def finished(
        self,
        status: UpdateService.UpdateStatus,
        task: Optional[QgsTask],
        plan: Optional["RdsPlan"],
        params: Optional[DistrictUpdateParams],
        exception: Optional[Exception],
    ):
        if status == UpdateService.UpdateStatus.SUCCESS:
            plan.distLayer.reload()
            reader = DistrictReader(plan.distLayer, plan.distField, plan.popField, plan.districtColumns)
            reader.loadDistricts(plan)

            trigger: MetricTriggers = 0
            if params.includeDemographics:
                trigger |= MetricTriggers.ON_UPDATE_DEMOGRAPHICS
            if params.includeGeometry:
                trigger |= MetricTriggers.ON_UPDATE_GEOMETRY

            self._metricsService.update(
                plan,
                False,
                trigger=trigger,
                populationData=params.populationData,
                districtData=params.districtData,
                geometry=params.geometry,
            )

        super().finished(status, task, plan, params, exception)

    def update(
        self,
        plan: "RdsPlan",
        force: bool = False,
        foreground: bool = False,
        *,
        districts: Optional[Iterable[int]] = None,
        includeDemographics=False,
        includeGeometry=False,
    ):
        """update aggregate district data from assignments, including geometry where requested

        :param plan: Plan to update
        :type plan: RdsPlan

        :param force: Cancel any pending update and begin a new update
        :type force: bool

        :param districts: Districts of plan to update if less than all districts
        :type districts: Iterable[int] | None

        :param needDemographics: Plan needs district demographics updated
        :type needDemographics: bool

        :param needGeometry: Plan needs district geometry and related metrics updated
        :type needGeometry: bool

        """
        if not (includeDemographics or includeGeometry):
            return None

        return super().update(
            plan,
            force,
            foreground,
            updateDistricts=districts,
            includeDemographics=includeDemographics,
            includeGeometry=includeGeometry,
        )

    def watchPlan(self, plan: "RdsPlan"):
        if plan.assignLayer:
            self._beforeCommitSignals.setMapping(plan.assignLayer, plan)
            self._afterCommitSignals.setMapping(plan.assignLayer, plan)
            plan.assignLayer.beforeCommitChanges.connect(self._beforeCommitSignals.map)
            plan.assignLayer.afterCommitChanges.connect(self._afterCommitSignals.map)

    def unwatchPlan(self, plan: "RdsPlan"):
        if plan.assignLayer:
            plan.assignLayer.beforeCommitChanges.disconnect(self._beforeCommitSignals.map)
            plan.assignLayer.afterCommitChanges.disconnect(self._afterCommitSignals.map)
            self._beforeCommitSignals.removeMappings(plan.assignLayer)
            self._afterCommitSignals.removeMappings(plan.assignLayer)

    def checkForChangedAssignments(self, plan: "RdsPlan"):
        dindex = plan.assignLayer.fields().lookupField(plan.distField)
        if dindex == -1:
            return

        new = {}
        changedAttrs: dict[int, dict[int, Any]] = plan.assignLayer.editBuffer().changedAttributeValues()
        for fid, attrs in changedAttrs.items():
            for fld, value in attrs.items():
                if fld == dindex:
                    new[fid] = value

        old = {f[dindex] for f in plan.assignLayer.dataProvider().getFeatures(QgsFeatureRequest(list(new.keys())))}
        self._updateDistricts[plan] = set(new.values()) | old

    def startUpdateDistricts(self, plan: "RdsPlan"):
        if self._updateDistricts[plan]:
            self.update(
                plan, True, districts=self._updateDistricts[plan], includeDemographics=True, includeGeometry=True
            )
            del self._updateDistricts[plan]
