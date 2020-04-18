import abc
import functools
import logging
import warnings
from typing import Set, Callable, Optional

import cocotb
import wrapt
from cocotb.bus import Bus
from cocotb.handle import SimHandleBase

from cocotbext.interfaces import signal as cis

class InterfaceProtocolError(Exception):
    pass


class InterfacePropertyError(ValueError):
    pass


class Filter(object):
    """
    Decorator used to setup methods provided as `Signal` filters e.g. for logical validation.
    """

    def __init__(self, cname: str):
        self.cname = cname

    @wrapt.decorator
    def __call__(self, wrapped, instance, args, kwargs):
        self.fn = wrapped
        instance._add_filter(self)
        return wrapped(*args, **kwargs)

    def __eq__(self, other):
        if not isinstance(other, Filter): return NotImplemented
        return self.cname == other.cname

    def __str__(self):
        return f"{self.__class__.__name__}({self.cname})"


class BaseInterface(object, metaclass=abc.ABCMeta):


    def __str__(self):
        return f"{self.__class__.__name__} interface"

    def __repr__(self):
        return self.__str__()

    def __contains__(self, item):
        """Used for membership testing of `Signal` items."""
        if hasattr(self, '_signals'):
            if isinstance(item, cis.Signal):
                return any([s.name == item.name for s in self.signals])
            elif isinstance(item, str):
                return any([s.name == item for s in self.signals])

        return False

    @classmethod
    @abc.abstractmethod
    def specification(cls) -> Set[cis.Signal]:
        """Returns the s specifications for this interface. Should be extended by child class."""
        pass

    @abc.abstractmethod
    def __init__(self,
                 entity: SimHandleBase,
                 bus_name: Optional[str] = None,
                 bus_separator: Optional[str] = "_",
                 log_level: int = logging.INFO) -> None:
        """Should be extended by child class."""

        self._log = cocotb.SimLog(f"cocotbext.interfaces.{str(self)}", id(self))
        self.log.setLevel(log_level)

        self._filters = set()
        self._specify(self.specification())

        # TODO: (redd@) Remove bus; account for naming variations e.g. w/ _n suffix
        self._bus = Bus(
            entity, bus_name, [s.name for s in self.specification() if s.required],
            [s.name for s in self.specification() if not s.required], bus_separator)

        # Instantiate signals on bus, add provided filters
        for s in self.signals:
            if s.name in self._bus._signals:
                s.handle = self._bus._signals[s.name]
                for f in self.filters:
                    if f.cname == s.name:
                        s.filter = f


    @property
    def log(self) -> logging.Logger: return self._log

    @property
    def signals(self) -> Set[cis.Signal]:
        return self._signals

    @property
    def controls(self) -> Set[cis.Control]:
        return set(c for c in self.signals if isinstance(c, cis.Control))

    @property
    def pmin(self) -> Optional[int]:
        return min(c.precedence for c in self.controls) if self.controls else None

    @property
    def pmax(self) -> Optional[int]:
        return max(c.precedence for c in self.controls) if self.controls else None

    @property
    def root(self) -> Set[cis.Control]:
        return set(c for c in self.controls if c.precedence == self.pmin)

    @property
    def base(self) -> Optional[Set[cis.Control]]:
        return set(c for c in self.controls if c.precedence == self.pmax)

    def _specify(self, spec: Set[cis.Signal], precedes: bool = False):
        """
        Incorporate specifications into interface.

        Args:
            spec: `Signal` instances to add to interface specification.
            precedes: Asserted if `Control` instances within `spec` behaviorally-precede those
            currently specified in self._signals.
        """

        if not hasattr(self, '_signals'):
            self._signals = set()

        if any(s in self for s in spec):
            raise ValueError(f"Duplicate signals specified: {spec}")

        # Consider relative precedence for new Controls
        cspec = set(s for s in spec if isinstance(s, cis.Control))
        if cspec:
            offset = max(cspec) if precedes else self.pmax
            for c in (self.controls if precedes else cspec):
                c.precedence += offset

        # Bind new Signal instances (they are descriptors)
        for s in spec:
            self._signals.add(s)
            setattr(self, s.name, s)

    def _txn(self, d: Optional[cis.Direction] = None) -> Set:
        """
        Returns names of signals in logical transactions. Optionally filter by direction.
        Args:
            d: If specified, matches parallel to d.
        """
        cnd = lambda s: s.instantiated and not s.meta and (True if d is None else s.direction == d)
        return set(s.name for s in self.signals if cnd(s))

    @property
    def filters(self) -> Set[Filter]:
        return self._filters

    def _add_filter(self, val: Filter) -> None:
        if val in self.filters:
            warnings.warn(f"Duplicate filter received; overwriting {str(val)}")
        self._filters.add(val)
