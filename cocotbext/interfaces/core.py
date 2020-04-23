import abc
import warnings
from typing import Set, Optional

import cocotb as c

import cocotbext.interfaces as ci

_LOG = c.SimLog(__name__)

class BaseInterface(object, metaclass=abc.ABCMeta):

    def __str__(self):
        return f"<{self.family}-{self.__class__.__name__}>"

    def __repr__(self):
        return f"<{self.__class__.__name__}(entity={str(self.entity)},family={self.family}," \
               f"signals={repr(self.signals)},floor={str(self.floor)}, ceiling={str(self.ceiling)}," \
               f"filters={repr(self.filters)})>"


    def __contains__(self, item):
        """Used for membership testing of `Signal` items."""
        if hasattr(self, '_signals'):
            if isinstance(item, ci.signal.Signal):
                return any([s.name == item.name for s in self.signals])
            elif isinstance(item, str):
                return any([s.name == item for s in self.signals])

        return False

    # TODO: (redd@) Rethink how users should index signals
    def __getitem__(self, key):
        """Used to look up signals"""
        return next(x for x in self.signals if x.name == key)

    @classmethod
    @abc.abstractmethod
    def specification(cls) -> Set[ci.signal.Signal]:
        """Returns the s specifications for this interface. Should be extended by child class."""
        pass

    @abc.abstractmethod
    def __init__(self,
                 entity: c.handle.SimHandleBase,
                 bus_name: Optional[str] = None,
                 bus_separator: str = "_",
                 family: Optional[str] = None,
                 log_level: Optional[int] = None) -> None:
        """Should be extended by child class."""

        self._entity = entity
        self._family = family.capitalize() if family else None

        if log_level is not None:
            _LOG.setLevel(log_level)

        self._filters = set()
        self._specify(
            self.specification(),
            bus_name=bus_name,
            bus_separator=bus_separator
        )

        _LOG.info(f"New {repr(self)}")

    @property
    def entity(self) -> c.handle.SimHandleBase: return self._entity

    @property
    def family(self) -> Optional[str]:
        return self._family

    @property
    def signals(self) -> Set[ci.signal.Signal]:
        return self._signals

    @property
    def controls(self) -> Set[ci.signal.Control]:
        return set(c for c in self.signals if isinstance(c, ci.signal.Control))

    @property
    def pmin(self) -> Optional[int]:
        return min(c.precedence for c in self.controls) if self.controls else None

    @property
    def pmax(self) -> Optional[int]:
        return max(c.precedence for c in self.controls) if self.controls else None

    @property
    def floor(self) -> Set[ci.signal.Control]:
        return set(c for c in self.controls if c.precedence == self.pmin)

    @property
    def ceiling(self) -> Optional[Set[ci.signal.Control]]:
        return set(c for c in self.controls if c.precedence == self.pmax)

    def _specify(self, spec: Set[ci.signal.Signal], precedes: bool = False,
                 bus_name: Optional[str] = None,
                 bus_separator: str = "_"):
        """
        Incorporate specifications into interface.

        Args:
            spec: `Signal` instances to add to interface specification.
            precedes: Asserted if `Control` instances within `spec` behaviorally-precede those
            currently specified in self._signals.
        """

        # TODO: (redd@) array_idx; account for naming variations e.g. w/ _n suffix
        def alias(s: ci.signal.Signal): return (bus_name + bus_separator if bus_name else '') + s.name

        if not hasattr(self, '_signals'):
            self._signals = set()

        if any(s in self for s in spec):
            raise ValueError(f"Duplicate signals specified: {repr(spec)}")

        # Consider relative precedence for new Controls
        cspec = set(s for s in spec if isinstance(s, ci.signal.Control))
        if cspec:
            offset = max(cspec).precedence if precedes else (self.pmax if self.pmax else 0)
            for c in (self.controls if precedes else cspec):
                c.precedence += offset

        # Instantiate signals, bind filters
        for s in spec:
            if not hasattr(self.entity, alias(s)):
                if s.required:
                    raise ci.InterfaceProtocolError(f"{str(self)} missing required signal: {str(s)}")

                _LOG.debug(f"{str(self)} ignoring optional missing signal: {str(s)}")
            else:
                s.handle = getattr(self.entity, alias(s))
            for f in self.filters:
                if f.cname == s.name:
                    s.filter = f
            self._signals.add(s)

        _LOG.debug(f"{str(self)} applied: {str(spec)}")

    def _txn(self, primary: Optional[bool] = None) -> Set[str]:
        """
        Returns names of signals in logical transactions. Optionally filter by direction.
        Args:
            primary: If True, False direction must be `Direction:FROM_PRIMARY`,
            `Direction:TO_PRIMARY`, respectively.
        """
        d = ci.signal.Direction.FROM_PRIMARY if primary else \
            (ci.signal.Direction.BIDIRECTIONAL if primary is None else ci.signal.Direction.TO_PRIMARY)

        cnd = lambda s: s.instantiated and not s.meta and s.direction == d
        return set(s.name for s in self.signals if cnd(s))

    @property
    def filters(self) -> Set[ci.decorators.filter]:
        return self._filters

    def _add_filter(self, val: ci.decorators.filter) -> None:
        if val in self.filters:
            warnings.warn(f"Duplicate filter received; overwriting {repr(val)}")
        self._filters.add(val)
        _LOG.info(f"{str(self)} applied: {repr(val)}")
