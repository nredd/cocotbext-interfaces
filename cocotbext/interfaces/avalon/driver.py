import abc
from abc import ABCMeta
from typing import Dict

from cocotb.drivers import Driver
from cocotb.triggers import RisingEdge

from cocotbext.interfaces.avalon import BaseSynchronousModel
from cocotbext.interfaces.avalon.streaming import StreamingInterface, SourceModel


class BaseDriver(Driver, metaclass=ABCMeta):
    """
    cocotb-style Driver implementation for synchronous Avalon interfaces.
    """

    def __str__(self):
        """Provide the name of the model"""
        return str(self.mod)

    @abc.abstractmethod
    def __init__(self, mod: BaseSynchronousModel) -> None:

        # TODO: (redd@) self.log
        super().__init__()
        self.mod = mod
        self.re = RisingEdge(self.mod.itf.clock)

    async def _driver_send(self, txn: Dict, sync: bool = True) -> None:
        """Implementation for BaseDriver.

        Args:
            transaction: The transaction to send.
        """

        if sync:
            await self.re

        await self.mod.tx(self.re, txn)


class AvalonST(BaseDriver):

    def __init__(self, *args, **kwargs) -> None:
        """Implementation for AvalonST."""

        # Args target Interface instance
        itf = StreamingInterface(*args, **kwargs)
        super().__init__(SourceModel(itf))

