# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - background task to calculate pending changes

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
from __future__ import annotations

import pathlib
from numbers import Number
from typing import (  # pylint: disable=no-name-in-module
    Optional,
    Self,
    overload
)

from qgis.core import QgsVectorLayer
from qgis.PyQt.QtCore import QObject

from ..models import (
    DeviationType,
    RdsDataField,
    RdsField,
    RdsPlan
)
from ..utils import (
    defaults,
    matchField,
    tr
)
from .planvalidator import PlanValidator


class BasePlanBuilder(PlanValidator):
    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._vap = None
        self._cvap = None
        self._geoPackagePath: pathlib.Path = None

    # pylint: disable=protected-access
    @classmethod
    def fromPlan(cls, plan: RdsPlan, parent: Optional[QObject] = None, **kwargs):
        instance = super().fromPlan(plan, parent, **kwargs)
        for f in instance._popFields:
            if instance._isVAP(f.field):
                instance._vap = f
            if instance._isCVAP(f.field):
                instance._cvap = f
        instance._geoPackagePath = plan.geoPackagePath
        return instance
    # pylint: enable=protected-access

    def setName(self, value: str):
        if not isinstance(value, str):
            raise ValueError(tr('Plan name must be a string'))

        self._name = value
        return self

    def setDescription(self, value: str):
        if value is not None and not isinstance(value, str):
            raise ValueError(tr('Plan description must be a string'))

        self._description = value
        return self

    def setNumDistricts(self, value: int):
        if not isinstance(value, int):
            raise ValueError(tr('Number of districts must be an integer'))

        if value < 2 or value > defaults.MAX_DISTRICTS:
            raise ValueError(
                tr('Invalid number of districts for plan: {value}').format(value=value))

        if self._numSeats == self._numDistricts or self._numSeats < value:
            self._numSeats = value

        self._numDistricts = value
        return self

    def setNumSeats(self, value: int):
        if not isinstance(value, int):
            raise ValueError(tr('Number of seats must be an integer'))

        self._numSeats = value
        return self

    def setDeviation(self, value: float):
        if not isinstance(value, Number):
            raise ValueError(tr('Deviation must be numeric'))

        self._deviation = float(value)
        return self

    def setDeviationType(self, value: DeviationType):
        self._deviationType = value
        return self

    def setGeoIdField(self, value: str):
        if value is not None and not isinstance(value, str):
            raise ValueError(tr('Geography ID field must be a string'))

        self._geoIdField = value
        if self._geoJoinField is None:
            self._geoJoinField = self._geoIdField
        if self._popJoinField is None:
            self._popJoinField = self._geoIdField
        return self

    def setGeoDisplay(self, value: str):
        if value is not None and not isinstance(value, str):
            raise ValueError(tr('Geography label must be a string'))

        self._geoIdCaption = value
        return self

    def setDistField(self, value: str):
        if value is not None and not isinstance(value, str):
            raise ValueError(tr('District field must be a string'))

        self._distField = value
        return self

    def setGeoLayer(self, value: QgsVectorLayer):
        if value is not None and not isinstance(value, QgsVectorLayer):
            raise ValueError(tr('Geography layer must be a vector layer'))

        if value is None and self._popLayer is not None:
            self._geoLayer = self._popLayer
        else:
            self._geoLayer = value

        if self._popLayer is None:
            self.setPopLayer(value)

        for f in self._geoFields:
            f.layer = self._geoLayer

        return self

    def setGeoJoinField(self, value: str):
        if value is not None and not isinstance(value, str):
            raise ValueError(tr('Geography join field must be a string'))

        self._geoJoinField = value if value is not None else self._geoIdField
        return self

    def setPopLayer(self, value: QgsVectorLayer):
        if value is not None and not isinstance(value, QgsVectorLayer):
            raise ValueError(tr('Population layer must be a vector layer'))

        if value is None and self._geoLayer is not None:
            self._popLayer = self._geoLayer
        else:
            self._popLayer = value

        if self._geoLayer is None:
            self.setGeoLayer(value)

        for f in self._popFields:
            f.layer = self._popLayer

        for f in self._dataFields:
            f.layer = self._popLayer

        return self

    def setPopJoinField(self, value: str):
        if value is not None and not isinstance(value, str):
            raise ValueError(tr('Population join field must be a string'))

        self._popJoinField = value if value is not None else self._geoIdField
        return self

    def setPopField(self, value: str):
        if value is not None and not isinstance(value, str):
            raise ValueError(tr('Population field must be a string'))

        self._popField = value
        return self

    def _checkNotDuplicate(self, field: RdsField, fieldList: list[RdsField]):
        if any(f.field == field.field for f in fieldList):
            return False

        return True

    def setPopFields(self, popFields: list[RdsField]):
        l = []
        for f in popFields:
            if not self._checkNotDuplicate(f, l):
                raise ValueError(tr('RdsField list contains duplicate fields'))

            if self._isVAP(f.field):
                self._vap = f
            if self._isCVAP(f.field):
                self._cvap = f
            f.layer = self._popLayer
            l.append(f)
        self._popFields = l
        return self

    def _isVAP(self, fieldName):
        return matchField(fieldName, self._popLayer, defaults.VAP_TOTAL_FIELDS)

    def _isCVAP(self, fieldName):
        return matchField(fieldName, self._popLayer, defaults.CVAP_TOTAL_FIELDS)

    @overload
    def appendPopField(self, field: str, isExpression: bool = False, caption: str = None) -> Self:
        ...

    @overload
    def appendPopField(self, field: RdsField) -> Self:
        ...

    def appendPopField(self, field, caption=None) -> Self:
        if isinstance(field, str):
            field = RdsField(self._popLayer, field, caption)
        elif not isinstance(field, RdsField):
            raise TypeError(
                tr('Attempt to add invalid field {field!r} to plan {plan}').
                format(field=field, plan=self._name)
            )

        if self._checkNotDuplicate(field, self._popFields):
            self._popFields.append(field)
            if self._isVAP(field.field):
                self._vap = field
            if self._isCVAP(field.field):
                self._cvap = field
        else:
            self.setError(
                tr('Attempt to add duplicate field {field} to plan {plan}').
                format(field=field.field, plan=self._name)
            )

        return self

    @overload
    def removePopField(self, field: RdsField) -> Self:
        ...

    @overload
    def removePopField(self, field: str) -> Self:
        ...

    @overload
    def removePopField(self, field: int) -> Self:
        ...

    def removePopField(self, field) -> Self:
        if isinstance(field, RdsField):
            if not field in self._popFields:
                raise ValueError(
                    tr('Could not remove field {field}. RdsField not found in plan {plan}.').
                    format(field=field.field, plan=self._name)
                )
        elif isinstance(field, str):
            for f in self._popFields:
                if f.field == field:
                    field = f
                    break
            else:
                raise ValueError(
                    tr('Could not remove field {field}. RdsField not found in plan {plan}.').
                    format(field=field, plan=self._name)
                )
        elif isinstance(field, int):
            if 0 <= field < len(self._popFields):
                field = self._popFields[field]
            else:
                raise ValueError(tr('Invalid index passed to RdsPlan.removePopField'))
        else:
            raise ValueError(tr('Invalid index passed to RdsPlan.removePopField'))

        self._popFields.remove(field)
        return self

    def setDataFields(self, dataFields: list[RdsDataField]):
        l = []
        for f in dataFields:
            if not self._checkNotDuplicate(f, l):
                raise ValueError(tr('RdsField list contains duplicate fields'))

            f.layer = self._popLayer
            l.append(f)
        self._dataFields = l
        return self

    @overload
    def appendDataField(
        self,
        field: str,
        caption: str = None,
        sumField: bool = True,
        pctBase: Optional[str] = None
    ) -> Self:
        ...

    @overload
    def appendDataField(self, field: RdsDataField) -> Self:
        ...

    def appendDataField(self, field, caption=None, sumField=True, pctBase=None) -> Self:
        if isinstance(field, str):
            if pctBase is None:
                if self._vap and matchField(field, self._popLayer, defaults.VAP_FIELDS):
                    pctBase = self._vap.field
                elif self._cvap and matchField(field, self._popLayer, defaults.CVAP_FIELDS):
                    pctBase = self._cvap.field
            field = RdsDataField(self._popLayer, field, caption, sumField=sumField, pctBase=pctBase)
        elif not isinstance(field, RdsDataField):
            raise TypeError(
                tr('Field must by an RdsField or the name of a field').
                format(field=field, plan=self._name)
            )

        if self._checkNotDuplicate(field, self._dataFields):
            self._dataFields.append(field)
        else:
            self.setError(
                tr('Attempt to add duplicate field {field} to plan {plan}').
                format(field=field.field, plan=self._name)
            )

        return self

    @overload
    def removeDataField(self, field: str) -> Self:
        ...

    @overload
    def removeDataField(self, field: RdsDataField) -> Self:
        ...

    @overload
    def removeDataField(self, field: int) -> Self:
        ...

    def removeDataField(self, field) -> Self:
        if isinstance(field, RdsDataField):
            if not field in self._dataFields:
                raise ValueError(
                    tr('Could not remove field {field}. RdsField not found in plan {plan}.').
                    format(field=field.field, plan=self._name)
                )
        elif isinstance(field, str):
            for f in self._dataFields:
                if f.field == field:
                    field = f
                    break
            else:
                raise ValueError(
                    tr('Could not remove field {field}. RdsField not found in plan {plan}.').
                    format(field=field, plan=self._name)
                )
        elif isinstance(field, int):
            if 0 <= field < len(self._dataFields):
                field = self._dataFields[field]
            else:
                raise ValueError(tr('Invalid index passed to RdsPlan.removeDataField'))
        else:
            raise ValueError(tr('Invalid index passed to RdsPlan.removeDataField'))

        self._dataFields.remove(field)
        return self

    def setGeoFields(self, geoFields: list[RdsField]):
        l = []
        for f in geoFields:
            if not self._checkNotDuplicate(f, l):
                raise ValueError(tr('RdsField list contains duplicate fields'))

            f.layer = self._geoLayer
            l.append(f)

        self._geoFields = l
        return self

    @overload
    def appendGeoField(self, field: str, caption: str = None) -> Self:
        ...

    @overload
    def appendGeoField(self, field: RdsField) -> Self:
        ...

    def appendGeoField(self, field, caption=None) -> Self:
        if isinstance(field, str):
            field = RdsField(self._geoLayer, field, caption)
        elif not isinstance(field, RdsField):
            raise ValueError(
                tr('Attempt to add invalid field {field!r} to plan {plan}').
                format(field=field, plan=self._name)
            )

        if self._checkNotDuplicate(field, self._geoFields):
            self._geoFields.append(field)
        else:
            self.setError(
                tr('Attempt to add duplicate field {field} to plan {plan}').
                format(field=field.field, plan=self._name)
            )

        return self

    @overload
    def removeGeoField(self, field: RdsField) -> Self:
        ...

    @overload
    def removeGeoField(self, field: str) -> Self:
        ...

    @overload
    def removeGeoField(self, field: int) -> Self:
        ...

    def removeGeoField(self, field) -> Self:
        if isinstance(field, RdsField):
            if not field in self._geoFields:
                raise ValueError(
                    tr('Could not remove field {field}. RdsField not found in plan {plan}.').
                    format(field=field.field, plan=self._name)
                )
        elif isinstance(field, str):
            for f in self._geoFields:
                if f.field == field:
                    field = f
                    break
            else:
                raise ValueError(
                    tr('Could not remove field {field}. RdsField not found in plan {plan}.').
                    format(field=field, plan=self._name)
                )
        elif isinstance(field, int):
            if 0 <= field < len(self._geoFields):
                field = self._geoFields[field]
            else:
                raise ValueError(tr('Invalid index passed to RdsPlan.removeGeoField'))
        else:
            raise ValueError(tr('Invalid index passed to RdsPlan.removeGeoField'))

        self._geoFields.remove(field)
        return self
