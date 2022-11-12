import pathlib
import subprocess
import sys
import time
import math

import pytest

import yaqc
import yaqd_core
from yaqd_core import testing


fake_sensor_config = pathlib.Path(__file__).parent / "fake-sensor-config.toml"
watchdog_config = pathlib.Path(__file__).parent / "watchdog-config.toml"


@testing.run_daemon_entry_point("fake-sensor", config=fake_sensor_config)
@testing.run_daemon_entry_point("watchdog", config=watchdog_config)
def test_online():
    c = yaqc.Client(36001)
    time.sleep(2)
    assert c.get_measured()["sensor_online"]


@testing.run_daemon_entry_point("watchdog", config=watchdog_config)
def test_offline():
    c = yaqc.Client(36001)
    time.sleep(2)
    print(c.get_measured())
    assert not c.get_measured()["sensor_online"]


if __name__ == "__main__":
    test_online()
    test_offline()
