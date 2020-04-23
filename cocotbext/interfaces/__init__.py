
class InterfaceProtocolError(Exception):
    pass


class InterfacePropertyError(ValueError):
    pass

import logging

import cocotb

# Base logger for module
cocotb.SimLog(f"cocotbext.interfaces").setLevel(logging.INFO)

from . import (
    decorators,
    adapters,
    signal,
    core,
    model,
)
