import abc
from typing import Callable, Optional

import cocotb
from cocotb.monitors import Monitor
from cocotb.triggers import RisingEdge

import cocotbext.interfaces as ci
import cocotbext.interfaces.avalon as cia
import cocotbext.interfaces.avalon.streaming as cias


class BaseMonitor(Monitor, metaclass=abc.ABCMeta):
    """
    cocotb-style Monitor implementation for synchronous Avalon interfaces.
    """

    def __str__(self):
        return str(self.model)

    @abc.abstractmethod
    def __init__(self, model: cia.BaseSynchronousModel, callback: Optional[Callable] = None) -> None:
        self._model = model

        # TODO: (redd@) self.log
        super().__init__(callback)

    @property
    def model(self) -> cia.BaseSynchronousModel: return self._model

    @cocotb.coroutine
    async def _monitor_recv(self) -> None:
        """Implementation for BaseMonitor"""
        txn = await self.model.rx()
        self._recv(txn)


class AvalonST(BaseMonitor):

    def __init__(self, *args, callback: Optional[Callable] = None, **kwargs) -> None:
        """Implementation for AvalonST."""

        # Args target Interface instance
        itf = cias.StreamingInterface(*args, **kwargs)
        super().__init__(cias.PassiveSinkModel(itf), callback)
