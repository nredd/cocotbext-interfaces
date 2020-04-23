
class InterfaceProtocolError(Exception):
    pass


class InterfacePropertyError(ValueError):
    pass

import logging

import cocotb

# TODO: (redd@) Add consistent arg-based log setup for class instances

# Base logger for module
_LOG = cocotb.SimLog(__name__)
_LOG.setLevel(logging.DEBUG)
_LOG.addHandler(logging.FileHandler('interfaces.log', 'w+'))

from . import (
    decorators,
    adapters,
    signal,
    core,
    model,
)
