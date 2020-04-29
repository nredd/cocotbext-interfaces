from typing import Optional, Union, Awaitable

import cocotb as c
import cocotb.triggers as ct
import pprint as p
from typing import Optional, Union
import cocotbext.interfaces as ci

class reaction(ci.Pretty):
    """
    Decorator for specifying coroutines that are  `BaseModel`)
    as behavioral reactions.
    """

    @property
    def cname(self) -> str: return self._cname

    @property
    def val(self) -> bool: return self._val

    @property
    def force(self) -> bool: return self._force

    @property
    def smode(self) -> ct.Trigger: return self._smode

    def __init__(self, cname: str, val: bool,
                 force: bool = False,
                 smode: ct.Trigger = ct.ReadOnly):

        super().__init__()
        self._cname = cname
        self._val = val
        self._force = force
        self._smode = smode

    def __call__(self, f: Awaitable):
        f.reaction = True
        f.cname = self.cname
        f.val = self.val
        f.force = self.force
        f.smode = self.smode
        self.log.info(f"{str(self)} detected: {f}")
        return f



# TODO: (redd@) Redo this
class filter(object):
    """
    Decorator used for specifying methods (bound to instances which inherit `BaseInterface`)
    as `Signal` filters e.g. for logical validation.
    """

    def __init__(self, cname: str):
        self.cname = cname

    def __call__(self, f):
        f.filter = True
        f.cname = self.cname
        _LOG.info(f"{str(self)} detected: {repr(f)}")
        return f

    # TODO: (redd@) Deprecate this
    def __eq__(self, other):
        if not isinstance(other, filter): return NotImplemented
        return self.cname == other.cname

    def __repr__(self):
        return f"<{self.__class__.__name__}(cname={self.cname})>"
