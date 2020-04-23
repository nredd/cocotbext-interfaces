from typing import Callable

import wrapt

import cocotb as c

# Base logger for module
_LOGGER = c.SimLog(f"cocotbext.interfaces.decorators")

# TODO: (redd@) Clean this

class reaction(object):
    """
    Decorator used to setup methods provided as behavioral reactions.
    """

    def __init__(self, cname: str, val: bool, force: bool = False):
        self.cname = cname
        self.val = val
        self.force = force

    def __call__(self, f):
        _LOGGER.info(f"Applying reaction decorator ({self.cname})")
        f.reaction = True
        f.cname = self.cname
        f.val = self.val
        f.force = self.force
        return f


class filter(object):
    """
    Decorator used to setup methods provided as `Signal` filters e.g. for logical validation.
    """

    def __init__(self, cname: str):
        self.cname = cname

    @wrapt.decorator
    def __call__(self, wrapped, instance, args, kwargs):
        self.fn = wrapped
        instance._add_filter(self)
        return wrapped(*args, **kwargs)

    def __eq__(self, other):
        if not isinstance(other, filter): return NotImplemented
        return self.cname == other.cname

    def __repr__(self):
        return f"<{self.__class__.__name__}(cname={self.cname},fn={self.fn})>"
