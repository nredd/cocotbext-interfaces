import abc
import collections
import inspect
import itertools
import logging


import pprint
from typing import List, Callable, Dict

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



class CroppingPrettyPrinter(pprint.PrettyPrinter):
    """From https://stackoverflow.com/questions/23567628/how-to-check-if-len-is-valid"""
    def __init__(self, *args, **kwargs):
        self.maxlist = kwargs.pop('maxlist', 10)
        super().__init__(*args, **kwargs)

    def _format(self, obj, stream, indent, allowance, context, level):
        if not isinstance(obj, str) and isinstance(obj, collections.Sized) and len(obj) > self.maxlist:
            if isinstance(obj, dict):
                out = dict(itertools.islice(obj.items(), self.maxlist))
            elif isinstance(obj, set):
                out = set(itertools.islice(obj, self.maxlist))
            else:
                out = list(itertools.islice(obj, self.maxlist))
            super()._format(out, stream, indent, allowance, context, level)
            return super()._format('...', stream, indent, allowance, context, level)

        # Let the original implementation handle anything else
        return super()._format(obj, stream, indent, allowance, context, level)


def pformat(object, indent=1, width=80, depth=None, *, compact=False, maxlist=5):
    """Format a Python object into a pretty-printed representation."""
    return CroppingPrettyPrinter(indent=indent, width=width, depth=depth,
                         compact=compact, maxlist=maxlist).pformat(object)


# TODO: (redd@) Pass args to Pretty from all subclasses
class Pretty(object, metaclass=abc.ABCMeta):
    """
    Useful defaults for logging.
    """

    @property
    def log(self) -> logging.getLoggerClass(): return self._log

    # TODO: (redd@) Revisit
    def _props(self) -> Dict:
        """Returns valid properties of object for logging."""
        def valid(p: property) -> bool:
            try:
                p.fget(self)
            except:
                return False
            return True

        predicate = lambda o: isinstance(o, property) and o.fget.__name__ != "log" and valid(o)
        def parse(p: property):
            val = p.fget(self)
            return str(val) if isinstance(val, Pretty) else val

        return {m[0]: parse(m[1]) for m in inspect.getmembers(type(self), predicate)}

    def __str__(self):
        name = self.name if hasattr(self, 'name') else None
        return f"<{self.__class__.__name__}({name})>" if name else f"<{self.__class__.__name__}>"

    def __repr__(self):
        plong = pformat(self._props(), width=80, depth=2, compact=True)
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
