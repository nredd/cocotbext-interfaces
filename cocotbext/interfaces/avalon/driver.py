import abc
from typing import Dict

import cocotb
from cocotb.drivers import Driver
from cocotb.triggers import RisingEdge

import cocotbext.interfaces as ci
import cocotbext.interfaces.avalon as cia
import cocotbext.interfaces.avalon.streaming as cias


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


class AvalonST(BaseDriver):

    def __init__(self, *args, **kwargs) -> None:
        """Implementation for AvalonST."""

        # Args target Interface instance
        itf = cias.StreamingInterface(*args, **kwargs)
        super().__init__(cias.SourceModel(itf))

