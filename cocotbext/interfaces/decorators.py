import cocotb as c
import cocotbext.interfaces as ci

_LOG = ci._LOG.getChild(__name__)
_LOG.propagate = True
_LOG.handlers.clear()

class reaction(object):
    """
    Decorator for specifying methods (bound to instances which inherit `BaseModel`)
    as behavioral reactions.
    """

    def __init__(self, cname: str, val: bool, force: bool = False):
        self.cname = cname
        self.val = val
        self.force = force

    def __call__(self, f):
        """
        Apply `cocotb.function` decorator such that reactions may be called within
        the event loop (itself a blocking coroutine) of some `BaseModel` object.
        """
        f.reaction = True
        f.cname = self.cname
        f.val = self.val
        f.force = self.force
        _LOG.info(f"{repr(self)} detected: {repr(f)}")
        return c.function(f)

    def __repr__(self):
        return f"<{self.__class__.__name__}(cname={self.cname},val={self.val},force={self.force})>"

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
        _LOG.info(f"{repr(self)} detected: {repr(f)}")
        return f

    # TODO: (redd@) Deprecate this
    def __eq__(self, other):
        if not isinstance(other, filter): return NotImplemented
        return self.cname == other.cname

    def __repr__(self):
        return f"<{self.__class__.__name__}(cname={self.cname})>"
