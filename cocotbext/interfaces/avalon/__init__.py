import abc
import enum
from typing import Optional, Dict, Set

import cocotb
from cocotb.handle import SimHandleBase
from cocotb.triggers import Trigger

import cocotbext.interfaces as ci
import cocotbext.interfaces.signal as cis
import cocotbext.interfaces.model as cim

# cis.Signal, cis.Control

class SynchronousEdges(enum.Enum):
    NONE = enum.auto()
    DEASSERT = enum.auto()
    BOTH = enum.auto()


class Clock(ci.BaseInterface):
    """
    Represents an Avalon Clock interface.
    """

    @classmethod
    def specification(cls) -> Set[cis.Signal]:
        return {
            cis.Signal('clk', required=True)
        }

    def __init__(self, *args,
                 rate: Optional[int] = None,
                 **kwargs) -> None:
        # TODO: (redd@) is associatedDirectClock needed? could be used to specify _clock domains
        if rate is not None and not 2 ** 32 - 1 >= rate >= 0:
            raise ci.InterfacePropertyError(
                f"{str(self)} spec. defines clockRate as 0-4294967295, was provided {rate}"
            )

        self._rate = rate
        super().__init__(*args, **kwargs)

    @property
    def rate(self) -> Optional[int]: return self._rate

    @property
    def rate_known(self) -> bool: return self._rate is not None


class Reset(ci.BaseInterface):
    """
    Represents an Avalon Reset interface.
    """

    @classmethod
    def specification(cls) -> Set[cis.Signal]:
        return {
            cis.Control('reset', required=True, flow_vals={False}, fix_vals={True}),
            cis.Control('reset_req', precedence=1),
        }

    def __init__(self, *args,
                 clock: Optional[Clock] = None,
                 edges: SynchronousEdges = SynchronousEdges.DEASSERT,
                 **kwargs) -> None:
        # TODO: (redd@) is associatedDirectResets needed? could be used to specify _reset domains

        self._clock = clock
        self._edges = edges

        super().__init__(*args, **kwargs)

    @property
    def clock(self) -> Optional[Clock]: return self._clock

    @property
    def edges(self) -> SynchronousEdges: return self._edges


class BaseSynchronousInterface(ci.BaseInterface, metaclass=abc.ABCMeta):
    """
    Represents a synchronous Avalon interface, which are defined to have associated
    Avalon Clock, Reset interfaces.
    """

    @abc.abstractmethod
    def __init__(self, entity, *args, **kwargs) -> None:
        # TODO: (redd@) rate, edges args
        super().__init__(entity, *args, family='avalon', **kwargs)

        self._clock = Clock(entity,  family='avalon', log_level=self.log.level)
        self._reset = Reset(entity, clock=self._clock,  family='avalon', log_level=self.log.level)
        self._specify(self._clock.signals)
        self._specify(self._reset.signals)


    @property
    def clock(self) -> SimHandleBase: return self._clock['clk']
    @property
    def reset(self) -> SimHandleBase: return self._reset['reset']


class BaseSynchronousModel(cim.BaseModel, metaclass=abc.ABCMeta):
    """
    Represents a model for synchronous Avalon interfaces, which are defined to have associated
    Avalon Clock, Reset interfaces.
    """

    @abc.abstractmethod
    def __init__(self, itf: BaseSynchronousInterface, *args, **kwargs) -> None:

        super().__init__(itf, *args, **kwargs)

    @property
    def itf(self) -> BaseSynchronousInterface:
        return self._itf

    async def tx(self, trig: Trigger, txn: Dict) -> None:
        """
        Blocking call to transmit a logical input as physical stimulus, driving
        pins of the interface. This (generally) consumes simulation time.
        """
        self._input(txn)
        while self.busy:
            await trig
            self._event_loop()

    async def rx(self, trig: Trigger) -> Dict:
        """
        Blocking call to sample/receive physical stimulus on pins of the interface and return the
        equivalent logical output. This (generally) consumes simulation time.
        """
        self.busy = True
        while self.busy:
            await trig
            self._event_loop()
        return self._output()
