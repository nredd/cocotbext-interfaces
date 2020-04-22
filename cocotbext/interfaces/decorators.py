import wrapt

class reaction(object):
    """
    Decorator used to setup function callbacks provided as behavioral reactions.
    """

    def __init__(self, cname: str, val: bool, force: bool = False):
        """
        Attr:
            cname:
            val:
            force: If asserted, reaction should be included even if `Control` is not instantiated.
            This effectively creates a 'virtual' precedence level for `Control`.
        """
        # TODO: (redd@) Expand to accept lists for cname, val; accept wildcard?
        self.cname = cname
        self.val = val
        self.force = force

    @wrapt.decorator
    def __call__(self, wrapped, instance, args, kwargs):
        self.fns = [wrapped]
        instance._add_reaction(self)
        return wrapped(*args, **kwargs)

    def __eq__(self, other):
        """

        An incompatibility occurs when two `Reaction`s have matching cname and at least one
        of them is forced.

        """
        if not isinstance(other, reaction):
            return NotImplemented
        return self.cname == other.cname and self.val == other.val and self.force == other.force

    def __repr__(self):
        return f"<{self.__class__.__name__}(cname={self.cname},fns={self.fns},force={self.force})>"


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
