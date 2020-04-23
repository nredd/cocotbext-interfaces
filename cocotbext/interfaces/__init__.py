import logging
import sys

# TODO: (redd@) Add consistent arg-based log setup for class instances

# Base logger for module
_LOG = logging.getLogger(__name__)
_LOG.setLevel(logging.DEBUG)
_LOG.handlers.clear()

fh = logging.FileHandler('interfaces.log')
fh.setLevel(logging.DEBUG)
sh = logging.StreamHandler(stream=sys.stdout)
sh.setLevel(logging.INFO)
sh.addFilter(logging.Filter())
_LOG.addHandler(fh)
_LOG.addHandler(sh)


class InterfaceProtocolError(Exception):
    pass

class InterfacePropertyError(ValueError):
    pass

from . import (
    decorators,
    adapters,
    signal,
    core,
    model,
)
