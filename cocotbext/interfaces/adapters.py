import abc
from typing import Dict, Optional, Callable

from cocotb.drivers import Driver
from cocotb.monitors import Monitor
from cocotb.decorators import coroutine

# TODO: (redd@) Add type annotations
class BaseDriver(Driver, metaclass=abc.ABCMeta):
    """
    cocotb-style Driver implementation for synchronous Avalon interfaces.
    """

    def __str__(self):
        return str(self.model)

    @abc.abstractmethod
    def __init__(self, model) -> None:
        self._model = model

        # TODO: (redd@) self.log
        super().__init__()

    @property
    def model(self): return self._model

    @coroutine
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
    def __init__(self, model, callback: Optional[Callable] = None) -> None:
        self._model = model

        # TODO: (redd@) self.log
        super().__init__(callback)

    @property
    def model(self): return self._model

    @coroutine
    async def _monitor_recv(self) -> None:
        """Implementation for BaseMonitor"""
        txn = await self.model.rx()
        self._recv(txn)