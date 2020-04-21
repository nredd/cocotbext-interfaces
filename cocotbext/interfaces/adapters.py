import abc
from typing import Dict, Optional, Callable

import cocotb
from cocotb.drivers import Driver
from cocotb.monitors import Monitor
from cocotb.triggers import RisingEdge

import cocotbext.interfaces as ci
import cocotbext.interfaces.avalon as cia


class BaseDriver(Driver, metaclass=abc.ABCMeta):
    """
    cocotb-style Driver implementation for synchronous Avalon interfaces.
    """

    def __str__(self):
        return str(self.model)

    @abc.abstractmethod
    def __init__(self, model: cia.BaseSynchronousModel) -> None:
        self._model = model

        # TODO: (redd@) self.log
        super().__init__()

    @property
    def model(self) -> cia.BaseSynchronousModel: return self._model

    @cocotb.coroutine
    async def _driver_send(self, txn: Dict, sync: bool = True) -> None:
        """Implementation for BaseDriver.

        Args:
            transaction: The transaction to send.
        """

        await self.model.tx(txn, sync)



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