import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    Qgis,
    QgsMessageLog
)

from redistricting.services.ErrorList import ErrorListMixin


class TestErrorListMixin:
    @pytest.fixture(autouse=True)
    def log(self, mocker: MockerFixture):
        mock = mocker.patch("redistricting.services.ErrorList.QgsMessageLog", spec=QgsMessageLog)
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
