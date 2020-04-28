import abc
import warnings
from typing import Set, Optional

import cocotb as c
import cocotbext.interfaces as ci

class BaseInterface(ci.Pretty, metaclass=abc.ABCMeta):

    @property
    def entity(self) -> c.handle.SimHandleBase: return self._entity

    @property
    def bus_name(self) -> str: return self._bus_name

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
        return min(self.controls).precedence if self.controls else None

    @property
    def pmax(self) -> Optional[int]:
        return max(self.controls).precedence if self.controls else None

    @property
    def floor(self) -> Set[ci.signal.Control]:
        return set(c for c in self.controls if c.precedence == self.pmin)

    @property
    def ceiling(self) -> Optional[Set[ci.signal.Control]]:
        return set(c for c in self.controls if c.precedence == self.pmax)


    @property
    def filters(self) -> Set[ci.decorators.filter]:
        return self._filters

    @classmethod
    @abc.abstractmethod
    def specification(cls) -> Set[ci.signal.Signal]:
        """Returns the s specifications for this interface. Should be extended by child class."""
        pass

    def _specify(self, spec: Set[ci.signal.Signal],
                 precedes: bool = False,
                 bus_name: Optional[str] = None,
                 bus_separator: str = "_"):
        """
        Incorporate specifications into interface.

        Args:
            spec: `Signal` instances to add to interface specification.
            precedes: Asserted if `Control` instances within `spec` behaviorally-precede those
            currently specified in self.controls.
        """

        # TODO: (redd@) array_idx; account for naming variations e.g. w/ _n suffix
        def alias(s: ci.signal.Signal):
            return f"{bus_name}{bus_separator}{s.name}" if bus_name else s.name

        if not hasattr(self, '_signals'):
            self._signals = set()

        if any(any(s.name == t.name for t in spec) for s in self.signals):
            raise ValueError(f"Duplicate signals specified: {repr(spec)}")

        # Consider relative precedence for new Controls
        if any(isinstance(s, ci.signal.Control) for s in spec):
            offset = max(c for c in spec if isinstance(c, ci.signal.Control)).precedence if precedes else self.pmax
            if precedes:
                for c in self.controls:
                    if offset is not None:
                        c.precedence += (offset + 1)
            else:
                for c in spec:
                    if isinstance(c, ci.signal.Control):
                        if offset is not None:
                            c.precedence += (offset + 1)

        # Instantiate signals, bind filters
        for s in spec:
            if not hasattr(self.entity, alias(s)):
                if s.required:
                    raise ci.InterfaceProtocolError(f"{self} missing required signal: {str(s)}")

                self.log.info(f"{self} ignoring optional: {str(s)}")
            elif not s.instantiated:
                s.handle = getattr(self.entity, alias(s))

                for f in self._filters:
                    if f.cname == s.name:
                        s.filter = f

            self._signals.add(s)
            self.log.debug(f"{self} applied: {str(spec)}")

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

    def _add_filter(self, val: ci.decorators.filter) -> None:
        if val in self.filters:
            warnings.warn(f"Duplicate filter received; overwriting {repr(val)}")
        self._filters.add(val)
        self.log.info(f"{self} applied: {repr(val)}")



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


    @abc.abstractmethod
    def __init__(self,
                 entity: c.handle.SimHandleBase,
                 bus_name: Optional[str] = None,
                 bus_separator: str = "_",
                 family: Optional[str] = None,
                 log_level: Optional[int] = None) -> None:
        """Should be extended by child class."""

        ci.Pretty.__init__(self) # Logging

        self._entity = entity
        self._family = family.capitalize() if family else None
        self._bus_name = bus_name

        if log_level is not None:
            self.log.setLevel(log_level)

        self._filters = set()
        self._specify(
            self.specification(),
            bus_name=bus_name,
            bus_separator=bus_separator
        )

        self.log.info(f"New {self}")
