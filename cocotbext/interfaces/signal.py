import functools
import enum
import warnings
from typing import Optional, Type, Union, Set, Iterator, Callable

import cocotb
from cocotb.binary import BinaryValue
from cocotb.handle import SimHandleBase

import cocotbext.interfaces as ci

_LOGGER = cocotb.SimLog(f"cocotbext.interfaces.signal")

class Direction(enum.Enum):
    FROM_PRIMARY = enum.auto(),
    TO_PRIMARY = enum.auto(),
    BIDIRECTIONAL = enum.auto(),


class Signal(object):
    """
    Representation of an interface signal; an instance may be considered a functional
    specifications of a physically-realizable digital signal to be used by some hardware
    interface.

    Wraps conventional cocotb signal handles such that an instance may be bound with a handle
    and provide logical validation (e.g. when sampling `BinaryValue` objects from handles) on
    top of simulation-level objects.
    """

    # allowed types for logical_type pulled from handle.ModifiableObject
    _allowed = Union[bool, int, BinaryValue]


    def __str__(self):
        return f"<{self.__class__.__name__}({self.name})>"

    def __repr__(self):
        return f"<{self.__class__.__name__}(name={self.name},required={self.required}," \
               f"instantiated={self.instantiated},active-high={self.logic_active_high}," \
               f"widths={self.widths},direction={self.direction},meta={self.meta}," \
               f"logical-type={str(self.logical_type)},handle={str(self.handle)}," \
               f"filter={self.filter})>"

    def capture(self) -> _allowed:

        if not self.instantiated:
            raise AttributeError(f"Signal ({str(self)}) not instantiated")

        val = self.handle.value
        if not val.is_resolvable:
            raise ci.InterfaceProtocolError(f"Signal ({str(self)}) is unresolvable")

        if not self.logic_active_high:
            val.assign(~val.integer & len(self.handle))

        if self.filter is not None:
            self.filter(val)

        _LOGGER.debug(f"{str(self)} captured sample: {repr(val)}")

        if self.logical_type == int:
            return val.integer
        elif self.logical_type == bool:
            return bool(val.integer)
        return val

    def drive(self, val: _allowed) -> None:
        if not self.instantiated:
            raise AttributeError(f"Signal ({str(self)}) not instantiated")

        if not isinstance(val, self.logical_type):
            raise TypeError(
                f"Signal ({str(self)}) has logical "
                f"type {self.logical_type} but was provided {type(val)}"
            )

        if self.filter is not None:
            self.filter(val)

        if not self.logic_active_high:
            if self.logical_type == BinaryValue:
                val.assign(~val.integer & len(self.handle))
            else:  # Valid for bool and int
                val = ~val & len(self.handle)

        self.handle <= (val if self.logical_type != bool else int(val))
        _LOGGER.debug(f"{str(self)} driven to: {repr(val)}")

    def __init__(self,
                 name: str, *args,
                 direction: Direction = Direction.FROM_PRIMARY,
                 meta: bool = False,
                 required: bool = False,
                 widths: Optional[Set[int]] = None,
                 logic_active_high: Optional[bool] = None,
                 logical_type: Type[_allowed] = bool,
                 **kwargs):
        """
        Args:
            name: Name of signal
            default_logical_val: assumed to be the equivalent of logical 0/low on all wires
        """


        if not name:
            raise ValueError(f"Signal names must be non-empty")

        if not widths:
            widths = {1}
        if any(w < 1 for w in widths):
            raise ValueError(f"Signal ({name}) widths must be positive")

        # TODO: (redd@) move this to itf.__init__
        if logic_active_high and name.endswith('_n'):
            warnings.warn(f"Signal ({name}) set logic to active-high but is suffixed by \'_n\'")
        elif logic_active_high is None:
            logic_active_high = not name.endswith('_n')

        self._name = name
        self._logic_active_high = logic_active_high
        self._required = required
        self._widths = widths
        self._direction = direction
        self._meta = meta
        self._logical_type = logical_type
        self._handle = None
        self._filter = None

        _LOGGER.info(f"New {repr(self)}")


    # Read-only
    @property
    def name(self):
        return self._name

    @property
    def instantiated(self):
        return self.handle is not None

    @property
    def logic_active_high(self):
        return self._logic_active_high

    @property
    def required(self):
        return self._required

    @property
    def widths(self):
        return self._widths

    @property
    def direction(self):
        return self._direction

    @property
    def meta(self):
        return self._meta

    @property
    def logical_type(self):
        return self._logical_type

    # Read-Write
    @property
    def handle(self):
        return self._handle

    @handle.setter
    def handle(self, val: SimHandleBase):
        if not len(val) in self.widths:
            raise ci.InterfacePropertyError(
                f"Invalid width ({len(val)}) for {str(val)}"
            )

        self._handle = val

        _LOGGER.debug(f"{str(self)} set handle: {repr(val)}")

    @property
    def filter(self):
        return self._filter

    @filter.setter
    def filter(self, val: Callable):
        # TODO: (redd@) Validation
        self._filter = val

        _LOGGER.debug(f"{str(self)} set filter: {repr(val)}")


@functools.total_ordering
class Control(Signal):
    """
    Represents a control signal, which affects the behavioral state hierarchy of an
    interface self. For each (distinct) logical value a `Control` (sample) may take on,
    there exists a corresponding (nested) state which a self may transition to during
    computation.

    Value states which may be behaviorally extended by the nests of `Control`s of lower
    precedence are denoted *flow* states--otherwise, denoted *fixed*.
    """

    def __repr__(self):
        return f"<{self.__class__.__name__}(\n" \
               f"name={self.name},\n " \
               f"required={self.required},\n " \
               f"instantiated={self.instantiated},\n " \
               f"active-high={self.logic_active_high},\n " \
               f"widths={self.widths},\n " \
               f"direction={self.direction},\n " \
               f"meta={self.meta},\n " \
               f"logical-type={self.logical_type},\n " \
               f"handle={self.handle},\n " \
               f"filter={self.filter}\n, " \
               f"allowance={self.allowance}\n, " \
               f"latency={self.latency}\n, " \
               f"precedence={self.precedence}\n, " \
               f"generated={self.generated}\n " \
               f")>\n"

    def __eq__(self, other):
        if not isinstance(other, Control):
            return NotImplemented
        return self.precedence == other.precedence

    def __hash__(self):
        return self.precedence

    def __lt__(self, other):
        if not isinstance(other, Control):
            return NotImplemented
        return self.precedence < other.precedence

    def capture(self) -> bool:
        if not self.generated:
            return super().capture()
        if self._cache is None:
            self.drive(self.next())
        return self._cache

    def drive(self, val: bool) -> None:
        if self.generated:
            self._cache = val
        super().drive(val)

    def clear(self) -> None:
        # TODO: (redd@) Raise error for non-generated Controls?
        self._cache = None

    # TODO: (redd@) possible to hook into GPI value-caches, remove _cache?
    # TODO: (redd@) How to define flow_vals, fix_vals for variable width+type control signals?
    # TODO: (redd@) How to support parallel (vs sibling) control signals?
    def __init__(
            self, *args,
            max_allowance: int = 0,
            max_latency: int = 0,
            precedence: int = 0,
            flow_vals: Optional[Set[bool]] = None,
            fix_vals: Optional[Set[bool]] = None,
            **kwargs):

        if max_allowance < 0:
            raise ValueError(f"Allowance cannot be negative")
        elif max_latency < 0:
            raise ValueError(f"Latency cannot be negative")

        self._max_allowance = max_allowance
        self._max_latency = max_latency

        self._generator = None
        self._flow_vals = flow_vals if flow_vals else {True}
        self._fix_vals = fix_vals if fix_vals else {False}

        self._allowance = 0
        self._latency = 0
        self._precedence = precedence

        # Control signals are meta by default; they aren't included in logical transactions
        super().__init__(*args, meta=True, **kwargs)

        if any(w > 1 for w in self.widths) or self.logical_type != bool:
            raise NotImplementedError(
                f"Control signals ({str(self)}) with more than "
                f"two (logical) values are not yet supported"
            )

    # Read-only
    @property
    def flow_vals(self):
        return self._flow_vals

    @property
    def fix_vals(self):
        return self._fix_vals

    @property
    def generated(self) -> bool:
        return self.generator is not None

    # Read-write
    @property
    def allowance(self):
        return self._allowance

    @allowance.setter
    def allowance(self, val: int):
        if not self._max_allowance >= val >= 0:
            raise ValueError(f"Outside defined range")
        self._allowance = val
        _LOGGER.debug(f"{str(self)} set allowance: {val}")

    @property
    def latency(self):
        return self._latency

    @latency.setter
    def latency(self, val: int):
        if not self._max_latency >= val >= 0:
            raise ValueError(f"Outside defined range")
        self._latency = val
        _LOGGER.debug(f"{str(self)} set latency: {val}")

    @property
    def precedence(self):
        return self._precedence

    @precedence.setter
    def precedence(self, val: int):
        self._precedence = val
        _LOGGER.debug(f"{str(self)} set precedence: {val}")

    @property
    def generator(self):
        return self._generator

    @generator.setter
    def generator(self, val: Iterator[bool]):
        if not self.instantiated:
            raise AttributeError(f"Cannot manipulate non-instantiated Control signal")
        self._generator = val
        self.clear()
        _LOGGER.debug(f"{str(self)} set generator: {repr(val)}")

    def next(self) -> bool:
        try:
            return bool(next(self.generator))
        except Exception as e:
            raise e  # TODO: (redd@) Do this better

