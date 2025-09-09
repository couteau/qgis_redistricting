"""QGIS Redistricting Plugin - base class for services managing updates in the background

        begin                : 2025-08-12
        git sha              : $Format:%H$
        copyright            : (C) 2025 by Cryptodira
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

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal, Optional, Union, overload

import geopandas as gpd
import pandas as pd
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeedback,
    QgsMessageLog,
    QgsTask,
    QgsVectorLayer,
)
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QObject, pyqtSignal

from ..errors import CanceledError
from ..models import DistrictColumns
from ..utils import LayerReader
from ..utils.misc import quote_identifier

if TYPE_CHECKING:
    from uuid import UUID

    from ..models import RdsPlan

if __debug__:
    from .tasks._debug import debug_thread


class UpdateStatus(Enum):
    PENDING = 0
    SUCCESS = 1
    CANCELED = 2
    ERROR = 3


@dataclass
class UpdateParams: ...


@dataclass
class UpdateTask:
    task: Optional[QgsTask] = None
    params: Optional[UpdateParams] = None


class UpdateException(Exception): ...


class IncrementalFeedback(QgsFeedback):
    def __init__(self, task: QgsFeedback):
        self.task = task
        self.start = 0
        self.stop = 100

    def setProgressIncrement(self, start: int, stop: int):
        self.task.setProgress(start)
        self.start = start
        self.stop = stop

    def updateProgress(self, total: int, count: int):
        if total != 0:
            self.task.setProgress(min(100, 100 * count / total))

    def setProgress(self, progress: float):
        return self.task.setProgress(self.start + progress * (self.stop - self.start) / 100)

    def cancel(self):
        self.task.cancel()

    def isCanceled(self):
        return self.task.isCanceled()

    def checkCanceled(self):
        if self.task.isCanceled():
            raise CanceledError()


class UpdateService(QObject):
    updateStarted = pyqtSignal("PyQt_PyObject")  # RdsPlan
    updateComplete = pyqtSignal("PyQt_PyObject")  # RdsPlan
    updateTerminated = pyqtSignal("PyQt_PyObject", "PyQt_PyObject")  # RdsPlan, Exception
    updateCanceled = pyqtSignal("PyQt_PyObject")  # RdsPlan

    paramsCls: type[UpdateParams] = UpdateParams

    def __init__(self, description: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._description = description
        self._updateTasks: dict[UUID, UpdateTask] = {}

    @overload
    def readLayer(
        self,
        layer: QgsVectorLayer,
        columns: Optional[list[str]] = ...,
        order: Optional[str] = ...,
        readGeometry: Literal[False] = ...,
        chunksize: int = ...,
        feedback: Optional[QgsFeedback] = None,
    ) -> pd.DataFrame: ...

    @overload
    def readLayer(
        self,
        layer: QgsVectorLayer,
        columns: Optional[list[str]] = ...,
        order: Optional[str] = ...,
        readGeometry: Literal[True] = ...,
        chunksize: int = ...,
        feedback: Optional[QgsFeedback] = None,
    ) -> gpd.GeoDataFrame: ...

    def readLayer(  # noqa: PLR0913
        self,
        layer: QgsVectorLayer,
        columns: Optional[list[str]] = None,
        order: Optional[str] = None,
        readGeometry: bool = True,
        chunksize: int = 0,
        feedback: Optional[QgsFeedback] = None,
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        reader = LayerReader(layer, feedback)
        return reader.read_layer(columns=columns, order=order, read_geometry=readGeometry, chunksize=chunksize)

    def _loadPopData(self, plan: "RdsPlan", feedback: Optional[QgsFeedback] = None) -> pd.DataFrame:  # noqa: PLR0912,PLR0915
        reader = LayerReader(plan.popLayer, feedback)
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(plan.popLayer))
        if reader.is_sql_capable:
            # read population data into a dataframe using sql if possible -- much faster to ask sql to evaluate
            # calculated fields that to potentially read a lot of data that is only used to perform calculations
            # and then discarded
            pop_cols = [plan.popJoinField, plan.popField]
            for f in plan.popFields:
                if f.isExpression():
                    f.prepare(context)
                    if f.expression.hasParserError():
                        continue
                    expr = f.field
                else:
                    expr = quote_identifier(f.field)
                pop_cols.append(f"{expr} as {quote_identifier(f.fieldName)}")

            for f in plan.dataFields:
                if f.isExpression():
                    f.prepare(context)
                    if f.expression.hasParserError():
                        continue
                    expr = f.field
                else:
                    expr = quote_identifier(f.field)
                pop_cols.append(f"{expr} as {quote_identifier(f.fieldName)}")

            sql = (
                f"SELECT {','.join(pop_cols)} FROM {reader.table_name} "  # noqa: S608
                f"ORDER BY {quote_identifier(plan.popJoinField)}"
            )
            popdf = reader.read_sql(sql, order=plan.popJoinField)
        else:
            remove = set()
            pop_cols = [plan.popJoinField, plan.popField]
            for f in plan.popFields:
                f.prepare(context)
                # determine which fields are necessary to evaluate calculated fields
                new_cols = [c for c in f.expression.referencedColumns() if c not in pop_cols]
                if f.isExpression():
                    remove.update(new_cols)
                else:
                    remove.difference_update(new_cols)

                pop_cols.extend(new_cols)

            for f in plan.dataFields:
                # determine which fields are necessary to evaluate calculated fields
                f.prepare(context)
                new_cols = [c for c in f.expression.referencedColumns() if c not in pop_cols]
                if f.isExpression():
                    remove.update(new_cols)
                else:
                    remove.difference_update(new_cols)

                pop_cols.extend(new_cols)

            popdf: pd.DataFrame = reader.read_layer(columns=pop_cols, order=plan.popJoinField, readGeometry=False)

            # evaluate the calculated fields - for most simple calculations, the expressions should be capable of
            # evaluation by pandas
            for f in plan.popFields:
                if f.isExpression():
                    popdf.loc[:, f.fieldName] = popdf.eval(f.field)
            for f in plan.dataFields:
                if f.isExpression():
                    popdf.loc[:, f.fieldName] = popdf.eval(f.field)

            # drop the fields that were only needed to evaluate calcualated fields
            popdf = popdf.drop(columns=remove)

        return popdf.rename(columns={plan.popField: str(DistrictColumns.POPULATION)})

    def _loadAssignments(  # noqa: PLR0912,PLR0915
        self,
        plan: "RdsPlan",
        includeGeoFields,
        includePopulationData: bool = True,
        includeGeometry: bool = False,
        feedback: Optional[QgsFeedback] = None,
    ):
        if feedback is not None:
            feedback = IncrementalFeedback(feedback)
            feedback.setProgressIncrement(0, 50 if includePopulationData else 100)

        cols = [plan.distField]
        if includeGeoFields:
            cols += plan.geoFields.keys()

        assignments = self.readLayer(
            plan.assignLayer, columns=[plan.geoIdField] + cols, readGeometry=includeGeometry, feedback=feedback
        ).set_index(plan.geoIdField)

        if includePopulationData:
            if feedback is not None:
                feedback.setProgressIncrement(50, 100)

            popdf = self._loadPopData(plan, feedback)
            assignments = assignments.join(popdf)
            cols += [DistrictColumns.POPULATION, *plan.popFields.keys(), *plan.dataFields.keys()]

        if includeGeometry:
            cols += ["geometry"]

        return assignments[cols]

    def _createParams(self, *args, **kwargs) -> UpdateParams:
        return self.paramsCls(*args, **kwargs)

    def _doUpdate(
        self, task: QgsTask, plan: "RdsPlan", params: UpdateParams
    ) -> tuple[QgsTask, "RdsPlan", UpdateParams]:
        if __debug__:
            debug_thread()

        self.updateStarted.emit(plan)
        try:
            params = self.run(task, plan, params)
            return (task, plan, params)
        except Exception as e:
            raise UpdateException(task, plan, params, e) from e

    def _doFinished(self, exception: Exception, args: Optional[tuple[QgsTask, "RdsPlan", UpdateParams]] = None):
        if args is None:
            if isinstance(exception, UpdateException):
                task, plan, params, exception = exception.args
            else:
                task = plan = params = None
        else:
            task, plan, params = args

        if args is None or task.status() == QgsTask.TaskStatus.Terminated:
            status = (
                UpdateStatus.CANCELED
                if (
                    exception is None
                    or isinstance(exception, CanceledError)
                    or exception.args[0] == "Task canceled"
                    or (params and params.task.isCanceled())
                )
                else UpdateStatus.ERROR
            )
        else:
            status = UpdateStatus.SUCCESS

        self.finished(status, task, plan, params, exception)

        if plan is not None:
            del self._updateTasks[plan.id]

    def planIsUpdating(self, plan: "RdsPlan"):
        if (
            plan.id in self._updateTasks
            and self._updateTasks[plan.id].task is not None
            and sip.isdeleted(self._updateTasks[plan.id].task)
        ):
            del self._updateTasks[plan.id]

        return (
            plan.id in self._updateTasks
            and self._updateTasks[plan.id].task is not None
            and self._updateTasks[plan.id].task.status() < QgsTask.TaskStatus.Complete
        )

    def cancelUpdate(self, plan: "RdsPlan"):
        if (
            plan.id in self._updateTasks
            and self._updateTasks[plan.id].task is not None
            and not sip.isdeleted(self._updateTasks[plan.id].task)
            and self._updateTasks[plan.id].task.canCancel()
        ):
            self._updateTasks[plan.id].task.cancel()
            del self._updateTasks[plan.id]

    def run(self, task: QgsTask, plan: "RdsPlan", params: UpdateParams) -> UpdateParams:
        return params

    def finished(
        self,
        status: UpdateStatus,
        task: Optional[QgsTask],
        plan: Optional["RdsPlan"],
        params: Optional[UpdateParams],
        exception: Optional[Exception],
    ):
        if status == UpdateStatus.CANCELED:
            self.updateCanceled.emit(plan)
        elif status == UpdateStatus.ERROR:
            QgsMessageLog.logMessage(f"{exception!r}", "Redistricting", Qgis.MessageLevel.Critical)
            self.updateTerminated.emit(plan, exception)
        else:
            self.updateComplete.emit(plan)

    def update(self, plan: "RdsPlan", force: bool = False, *args, **kwargs) -> UpdateParams:
        if self.planIsUpdating(plan):
            if force:
                self.cancelUpdate(plan)
            else:
                return self._updateTasks[plan.id]

        params = self._createParams(*args, **kwargs)
        if params is None:
            return None

        task = QgsTask.fromFunction(
            self._description, self._doUpdate, on_finished=self._doFinished, plan=plan, params=params
        )

        self._updateTasks[plan.id] = UpdateTask(task, params)
        QgsApplication.taskManager().addTask(task)
        return params
