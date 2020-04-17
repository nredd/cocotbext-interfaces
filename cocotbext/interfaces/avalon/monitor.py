from typing import Callable
import abc
from abc import ABCMeta
from typing import Optional

from cocotb.monitors import Monitor
from cocotb.triggers import RisingEdge

from cocotbext.interfaces.avalon import BaseSynchronousModel
from cocotbext.interfaces.avalon.streaming import StreamingInterface, PassiveSinkModel


class BaseMonitor(Monitor, metaclass=ABCMeta):
    """
    cocotb-style Monitor implementation for synchronous Avalon interfaces.
    """

    def __str__(self):
        """Provide the name of the model"""
        return str(self.mod)

    @abc.abstractmethod
    def __init__(self, mod: BaseSynchronousModel, callback: Optional[Callable] = None) -> None:
        # TODO: (redd@) self.log
        super().__init__(callback)
        self.mod = mod
        self.re = RisingEdge(self.mod.itf.clock)

    async def _monitor_recv(self) -> None:
        """Implementation for BaseMonitor"""
        txn = await self.mod.rx(self.re)
        self._recv(txn)


class AvalonST(BaseMonitor):

    def __init__(self, *args, callback: Optional[Callable] = None, **kwargs) -> None:
        """Implementation for AvalonST."""

        # Args target Interface instance
        itf = StreamingInterface(*args, **kwargs)
        super().__init__(PassiveSinkModel(itf), callback)
