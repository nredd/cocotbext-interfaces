import logging
import sys

from cocotb.log import SimLog, SimColourLogFormatter, SimLogFormatter
from cocotb.utils import want_color_output

def sim_log(name, id=None, level=logging.DEBUG):
    """ Like `cocotb.SimLog`, but with more handler setup."""
    # TODO: (redd@) Add more parameterization for handlers via arg

    name = name if id is None else f"{name}.{id}"
    new = SimLog(name)
    new.handlers = []
    new.setLevel(level)

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"{name}.log", "w+")
    ]
    for h in handlers:
        if want_color_output():
            h.setFormatter(SimColourLogFormatter())
        else:
            h.setFormatter(SimLogFormatter())
        new.addHandler(h)

    return new


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
