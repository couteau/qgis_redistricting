import pytest


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config):
    from .fixtures import Fixtures  # pylint: disable=import-outside-toplevel
    config.pluginmanager.register(Fixtures())
