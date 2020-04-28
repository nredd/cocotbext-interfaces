import abc
import inspect
import logging

import pprint
from cocotb.log import SimLogFormatter, SimColourLogFormatter, SimLog, SimBaseLog, SimTimeContextFilter, want_color_output

# Ad hoc logging
root = logging.getLogger()
fh = logging.FileHandler(__name__, 'w+')
fh.addFilter(SimTimeContextFilter())
fh.setFormatter(SimColourLogFormatter() if want_color_output() else SimLogFormatter())

def log(name, level, id=None):
    """ `cocotb.SimLog` with levels."""

    new = SimLog(name, id)
    new.setLevel(level)
    return new

# TODO: (redd@) Pass args to Pretty from all subclasses
class Pretty(object, metaclass=abc.ABCMeta):
    """
    Useful defaults for logging.
    """

    @property
    def log(self) -> logging.getLoggerClass(): return self._log

    # TODO: (redd@) Fix
    def __str__(self):
        properties = [p[1].fget() for p in inspect.getmembers(self, lambda o: isinstance(o, property))]
        pshort = pprint.pformat(pprint.saferepr(properties[:3]), width=40, depth=2, compact=True)
        return f"<{self.__class__.__name__}({pshort})>"

    def __repr__(self):
        properties = [p[1].fget() for p in inspect.getmembers(self, lambda o: isinstance(o, property))]
        plong = pprint.pformat(pprint.saferepr(properties), width=40, depth=2, compact=True)
        return f"<{self.__class__.__name__}({plong})>"

    @abc.abstractmethod
    def __init__(self, level=logging.INFO):
        self._log = log(f"{self.__module__}.{self.__class__.__name__}", level)



class InterfaceProtocolError(Exception):
    pass

class InterfacePropertyError(ValueError):
    pass

from . import (
    decorators,
    adapters,
    signal,
    core,
    model,
)
