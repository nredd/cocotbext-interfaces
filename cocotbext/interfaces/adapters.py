import abc
from typing import Dict, Optional, Callable

import cocotb as c
from cocotb.drivers import Driver
from cocotb.monitors import Monitor

# TODO: (redd@) Add type annotations
class BaseDriver(Driver, metaclass=abc.ABCMeta):
    """
    cocotb-style Driver implementation for synchronous Avalon interfaces.
    """

    @property
    def model(self): return self._model


    async def _driver_send(self, txn: Dict, sync: bool = True) -> None:
        """Implementation for BaseDriver.

        Args:
            transaction: The transaction to send.
        """

        await self.model.tx(txn, sync)


    def __str__(self):
        return str(self.model)

    @abc.abstractmethod
    def __init__(self, model) -> None:
        self._model = model

        # TODO: (redd@) self.log
        super().__init__()

class BaseMonitor(Monitor, metaclass=abc.ABCMeta):
    """
    cocotb-style Monitor implementation for synchronous Avalon interfaces.
    """


    @property
    def model(self): return self._model

    async def _monitor_recv(self) -> None:
        """Implementation for BaseMonitor"""
        txn = await self.model.rx()
        self._recv(txn)

    def __str__(self):
        return str(self.model)

    @abc.abstractmethod
    def __init__(self, model, callback: Optional[Callable] = None) -> None:
        self._model = model
        self.name = model.itf.bus_name
        # TODO: (redd@) self.log
        super().__init__(callback)
