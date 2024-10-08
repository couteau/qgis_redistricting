"""QGIS Redistricting Plugin - unit tests

Copyright 2022-2024, Stuart C. Naifeh

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
import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    Qgis,
    QgsMessageLog
)

from redistricting.services.errormixin import ErrorListMixin


class TestErrorListMixin:
    @pytest.fixture(autouse=True)
    def log(self, mocker: MockerFixture):
        mock = mocker.patch("redistricting.services.errormixin.QgsMessageLog", spec=QgsMessageLog)
        return mock

    def test_push_error_exception_logs_message(self, log: QgsMessageLog):
        errorlistmixin = ErrorListMixin()
        errorlistmixin.pushError(Exception("message"))
        log.logMessage.assert_called_with("message", "Redistricting", Qgis.Warning)
        assert errorlistmixin.error() == ("message", Qgis.Warning)

    def test_push_error_string_logs_message(self, log: QgsMessageLog):
        errorlistmixin = ErrorListMixin()
        errorlistmixin.pushError("message")
        log.logMessage.assert_called_once_with("message", "Redistricting", Qgis.Warning)
        assert errorlistmixin.error() == ("message", Qgis.Warning)

    def test_clear(self):
        errorlistmixin = ErrorListMixin()
        errorlistmixin.pushError("message")
        assert errorlistmixin.error() == ("message", Qgis.Warning)
        errorlistmixin.clearErrors()
        assert errorlistmixin.error() is None

    def test_set_error(self):
        errorlistmixin = ErrorListMixin()
        errorlistmixin.pushError("message")
        assert errorlistmixin.error() == ("message", Qgis.Warning)
        errorlistmixin.setError("other message")
        assert errorlistmixin.error() == ("other message", Qgis.Warning)
        assert len(errorlistmixin.errors()) == 1

    def test_push_error_with_level_logs_level(self, log: QgsMessageLog):
        errorlistmixin = ErrorListMixin()
        errorlistmixin.pushError(Exception("message"), Qgis.Critical)
        log.logMessage.assert_called_with("message", "Redistricting", Qgis.Critical)
        assert errorlistmixin.error() == ("message", Qgis.Critical)
