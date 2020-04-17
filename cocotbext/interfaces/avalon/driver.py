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
        """Provide the name of the model"""
        return str(self.mod)

    @abc.abstractmethod
    def __init__(self, mod: cia.BaseSynchronousModel) -> None:

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
        itf = cias.StreamingInterface(*args, **kwargs)
        super().__init__(cias.SourceModel(itf))

