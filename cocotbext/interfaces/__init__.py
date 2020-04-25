import abc
import inspect
import logging
import sys

import pprint
from cocotb.log import SimLog, SimColourLogFormatter, SimLogFormatter
from cocotb.utils import want_color_output # TODO: (redd@) How to point this to testbench's env vars?

def sim_log(name, level,
            shlevel=None,
            fhlevel=None,
            id=None):

    """ Like `cocotb.SimLog`, but with more handler setup."""

    # TODO: (redd@) lock logger before mutating
    name = name if id is None else f"{name}.{id}"
    new = SimLog(name)
    new.handlers = []
    new.setLevel(level)

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(level if shlevel is None else shlevel)

    fh = logging.FileHandler(f"{name}.log", "w+")
    fh.setLevel(level if fhlevel is None else fhlevel)

    for h in [sh, fh]:
        h.setFormatter(SimColourLogFormatter() if want_color_output() else SimLogFormatter())
        new.addHandler(h)

    return new

# TODO: (redd@) Pass args to Pretty from all subclasses
class Pretty(object, metaclass=abc.ABCMeta):
    """
    Useful defaults for logging.
    """
    # TODO: (redd@) Fix
    def __str__(self):
        properties = [p[1].fget() for p in inspect.getmembers(self, lambda o: isinstance(o, property))]
        pshort = pprint.pformat(pprint.saferepr(properties[:3]), width=40, depth=2, compact=True)
        return f"<{self.__class__.__name__}({pshort})>"

    def __repr__(self):
        properties = [p[1].fget() for p in inspect.getmembers(self, lambda o: isinstance(o, property))]
        plong = pprint.pformat(pprint.saferepr(properties), width=40, depth=2, compact=True)
        return f"<{self.__class__.__name__}({plong})>"

    @property
    def log(self) -> logging.getLoggerClass(): return self._log
        
    @abc.abstractmethod
    def __init__(self,
                 level=logging.DEBUG,
                 shlevel=None,
                 fhlevel=None):
        self._log = sim_log(
            f"{self.__module__}.{self.__class__.__name__}", level, shlevel, fhlevel)



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
