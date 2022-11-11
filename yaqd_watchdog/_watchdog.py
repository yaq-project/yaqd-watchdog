__all__ = ["Watchdog"]

import asyncio
import time
from typing import Dict, Any, List, Union
from dataclasses import dataclass
import yaqc
import socket

from yaqd_core import IsSensor, IsDaemon


class BaseCheck:
    def check(self) -> float:
        if "_remaining" not in self.__dict__:
            self._remaining = self.timeout
        if "_last" not in self.__dict__:
            self._last = time.time()
        if self._check():
            self._remaining = self.timeout
            self._last = time.time()
        else:
            self._remaining = max(0, self.timeout + (self._last - time.time()))
        return self._remaining


@dataclass
class OnlineCheck(BaseCheck):
    host: str
    port: int
    online: bool
    timeout: int
    state: bool = True

    def _check(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((self.host, self.port)) == 0


@dataclass
class AbsolutePositionCheck(BaseCheck):
    host: str
    port: int
    under: Union[float, None]
    over: Union[float, None]
    timeout: int

    def _check(self) -> bool:
        try:
            c = yaqc.Client(host=self.host, port=self.port)
            position = c.get_position()
            if self.over is not None:
                assert position >= self.over
            if self.under is not None:
                assert position <= self.under
            return True
        except Exception as e:
            print(e)
            return False


@dataclass
class PercentagePositionCheck(BaseCheck):
    host: str
    port: int
    percent_under = float
    percent_over = float
    delay = int


@dataclass
class SetPositionAction:
    host: str
    port: int
    position: float


@dataclass
class SetIdentifierAction:
    host: str
    port: int
    identifier: float


class Watchdog(IsSensor, IsDaemon):
    _kind = "watchdog"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        self._checks = {}
        for k, d in self._config["online_checks"].items():
            self._checks[k] = OnlineCheck(**d)
        for k, d in self._config["absolute_position_checks"].items():
            self._checks[k] = AbsolutePositionCheck(**d)
        for k, d in self._config["percentage_position_checks"].items():
            self._checks[k] = PercentagePositionCheck(**d)
        self._actions = {}
        for k, d in self._config["set_position_actions"].items():
            self._actions[k] = SetPositionAction(**d)
        for k, d in self._config["set_identifier_actions"].items():
            self._actions[k] = SetIdentifierAction(**d)

    async def update_state(self):
        while True:
            for k, check in self._checks.items():
                print(check, check.check())
            await asyncio.sleep(1)
