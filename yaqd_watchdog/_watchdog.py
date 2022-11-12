__all__ = ["Watchdog"]

import asyncio
import time
from typing import Dict, Any, List, Union
from dataclasses import dataclass
import yaqc  # type: ignore
import socket

from yaqd_core import IsSensor, IsDaemon


class BaseCheck:
    timeout: int

    def _check(self) -> bool:
        raise NotImplementedError

    def check(self) -> float:
        if "_remaining" not in self.__dict__:
            self._remaining = float(self.timeout)
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
    percent_under: float
    percent_over: float
    timeout: int

    def _check(self) -> bool:
        try:
            c = yaqc.Client(host=self.host, port=self.port)
            position = c.get_position()
            destination = c.get_destination()
            if self.percent_over is not None:
                assert position >= destination * (float(self.percent_over) / 100)
            if self.percent_under is not None:
                assert position <= destination * (float(self.percent_under) / 100)
            return True
        except Exception as e:
            print(e)
            return False


@dataclass
class SetPositionAction:
    host: str
    port: int
    position: float

    def trigger(self, checks: dict):
        try:
            c = yaqc.Client(host=self.host, port=self.port)
            c.set_position(self.position)
        except:
            pass


@dataclass
class SetIdentifierAction:
    host: str
    port: int
    identifier: float

    def trigger(self, checks: dict):
        try:
            c = yaqc.Client(host=self.host, port=self.port)
            c.set_identifier(self.identifier)
        except:
            pass


class Watchdog(IsSensor, IsDaemon):
    _kind = "watchdog"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        # checks
        self._checks = {}
        for k, d in self._config["online_checks"].items():
            self._checks[k] = OnlineCheck(**d)
        for k, d in self._config["absolute_position_checks"].items():
            self._checks[k] = AbsolutePositionCheck(**d)
        for k, d in self._config["percentage_position_checks"].items():
            self._checks[k] = PercentagePositionCheck(**d)
        # actions
        self._actions = {}
        for k, d in self._config["set_position_actions"].items():
            self._actions[k] = SetPositionAction(**d)
        for k, d in self._config["set_identifier_actions"].items():
            self._actions[k] = SetIdentifierAction(**d)
        # sensor stuff
        self._channel_names = list(self._checks.keys())
        self._channel_units = {k: "s" for k in self._channel_names}

    async def update_state(self):
        while True:
            starved = False
            # checks
            channels = dict()
            for k, check in self._checks.items():
                remaining = check.check()
                channels[k] = remaining
                if remaining == 0:
                    starved = True
            self._measurement_id += 1
            channels["measurement_id"] = self._measurement_id
            self._measured = channels
            # actions
            if starved:
                for k, action in self._actions.items():
                    action.trigger(self._measured)
            await asyncio.sleep(1)
