import abc
import functools
import itertools
import logging
from typing import List, Optional, Set, Dict, Iterable, Callable, Deque

import cocotb
import transitions
import wrapt
from transitions.extensions import HierarchicalMachine
from transitions.extensions.states import add_state_features, Tags, Volatile

import cocotbext.interfaces as ci
import cocotbext.interfaces.signal as cis

_LOGGER = cocotb.SimLog(f"cocotbext.interfaces.model")

class Reaction(object):
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
        if not isinstance(other, Reaction):
            return NotImplemented
        return self.cname == other.cname and self.val == other.val and self.force == other.force

    def __repr__(self):
        return f"\n<{self.__class__.__name__}(\n" \
               f"cname={self.cname},\n " \
               f"fns={self.fns}, \n" \
               f"force={self.force}\n" \
               f")>\n"


@add_state_features(Tags, Volatile)
class BaseModel(HierarchicalMachine, metaclass=abc.ABCMeta):
    # TODO: (redd@) refactor w/ AsyncMachine + async primitives? would improve performance

    def __str__(self):
        return f"<{str(self.itf)}-{self.__class__.__name__}>"

    def __repr__(self):
        return f"<{self.__class__.__name__}(\n" \
               f"itf={repr(self.itf)},\n " \
               f"primary={self.primary},\n " \
               f"reactions={repr(self.reactions)},\n " \
               f"nest={self.nest}\n " \
               f")>\n"

    @abc.abstractmethod
    def __init__(self, itf: ci.BaseInterface, primary: Optional[bool] = None) -> None:
        """Should be extended by child class."""

        self._reactions = set()
        self._itf = itf

        self._buff = {}
        self.busy = None

        self.primary = primary

        # TODO: (redd@) Override transitions logger?
        HierarchicalMachine.__init__(self,
                                     states=self.nest,
                                     initial='ROOT',
                                     queued=True,
                                     send_event=True)

        _LOGGER.info(f"New {repr(self)}")

    @property
    def itf(self) -> ci.BaseInterface:
        return self._itf

    @property
    def reactions(self) -> Set[Reaction]:
        return self._reactions

    def _add_reaction(self, val: Reaction) -> None:
        if any(r.cname == val.cname and r.force and val.force for r in self.reactions):
            raise ValueError(f"At most one control value reaction may be forced")
        if val in self.reactions:
            next(iter(self.reactions)).fns.extend(val.fns)
        else:
            self.reactions.add(val)

    # TODO: (redd@) Add more logging here
    # TODO: (redd@) Consider generated Controls wrt influences st only generated caches deleted
    @property
    def nest(self) -> Dict:
        """
        Generate states, transitions for behavioral interface model based on `itf.controls`.
        """

        # Tags:
        # flow - Denotes an accepted non-idle/operational (leaf) state
        # fix - Denotes an accepted idle/non-operational (leaf) state
        # wait - Denotes a temporary state
        # Lack of flow, fix tag indicates a non-accepted superstate; may have accepted children

        # Nested delay (volatile) states are allowed given that a parent control context persists

        # TODO: (redd@) Use dicts for transitions, not lists
        # TODO: (redd@) possible to properly delete cached control values w/ 'after' cb?s
        def node(
                name='BASE', tags=None, on_enter=None, on_exit=None, initial=None,
                children=None, transitions=None, volatile=None, hook=None,
                conditions=None, influences=None, reactions=None
        ):

            n = {
                'name': name,
                'tags': tags if tags is not None else [],
                'children': children if children is not None else [],
                'on_enter': on_enter if on_enter is not None  else [],
                'on_exit': on_exit if on_exit is not None else [],
                'transitions': transitions if transitions is not None else [],
                'conditions': conditions if conditions is not None else [],
                'influences': influences if influences is not None else [],
                'reactions': reactions if reactions is not None  else []
            }

            if initial:
                n['initial'] = initial
            if volatile is not None:
                n['volatile'] = volatile
            if hook is not None:
                n['hook'] = hook

            return n

        def is_flow(state) -> bool:
            return 'tags' in state and 'flow' in state['tags']

        def is_fix(state) -> bool:
            return 'tags' in state and 'fix' in state['tags']

        def is_leaf(state) -> bool:
            return not 'children' in state or not state['children']

        def get_flowers(nest):
            if not is_fix(nest):
                if is_leaf(nest) and is_flow(nest):
                    return nest
                return [get_flowers(c) for c in nest['children']]

        def flatten(ls) -> List:
            f = []
            for i in ls:
                f.extend(flatten(i)) if isinstance(i, list) else f.append(i)
            return f

        # TODO: (redd@) Refactor

        def nestify(ctrl: cis.Control, cond: List, infl: List, react: List) -> Dict:
            """
            Returns a nest representing the behavioral [sub-]state space induced by a given Control.

            Args:
                ctrl: Control to represent.
                cond: List of callbacks representing conditions prerequisite for entry. Each
                hook constrains a single parent or sibling control signal--together, they
                explicitly define a reference control input for behavioral context.
                infl: List of `Control` names representing those control signals whose
                samples/values must remain invariant within this nest; whenever a machine enters
                this nest, the caches of these `Control`s are emptied.
            """

            sample = lambda: ctrl.capture()
            is_fix = lambda _: sample() in ctrl.fix_vals
            is_flow = lambda _: sample() in ctrl.flow_vals

            def value(val, flow=True, delayed=False, cond=None, infl=None, react=None):
                """
                Returns a nest corresponding to a single, distinct control value.

                If a `Control` instance is delayed, the (state-level) behavioral effects of its
                signal transitions may be temporally postponed--assuming the external (behavioral)
                context remains invariant. A volatile nest is included to represent delayed states.
                Delayed states may be nested insofar as their behavioral contexts are preserved.


                Args:
                    val: Control value to consider
                    flow: If asserted, is flow_val
                    delayed: If asserted, state contains delay logic
                """

                # Positive, negative constraints for base, delayed substates respectively
                pcon = lambda _: sample() == val if flow else is_fix
                ncon = lambda _: sample() != val if flow else is_flow

                # Include reaction if defined
                match = next(
                    (r.fns for r in self.reactions if r.cname == ctrl.name and r.val == val), None)
                react = ([] if react is None else react) + ([] if match is None else match)

                n = node(
                    name=str(val).upper(),
                    conditions=cond,
                    influences=infl,
                    reactions=react,
                    initial='BASE',
                    children=[
                        node(tags=['flow' if flow else 'fix'],
                             influences=infl,
                             reactions=react,
                             conditions=cond + [pcon] if cond else [pcon])
                    ],
                    transitions=[
                        ['advance', 'BASE', None, cond + [pcon] if cond else [pcon]],
                    ]
                )

                if delayed:
                    subname = 'ALLOWANCE' if flow else 'LATENCY'
                    hook = f"{ctrl.name}_{subname.lower()}_count"

                    wait = lambda _: (ctrl.allowance if flow else ctrl.latency) > getattr(self, hook)
                    tick = lambda _: setattr(self, hook, getattr(self, hook) + 1)

                    n['children'] += [
                        node(
                            name=subname,
                            tags=['flow' if flow else 'fix', 'wait'],
                            volatile=int,
                            hook=hook,
                            influences=infl,
                            reactions=react,
                            conditions=cond + [ncon] if cond else [ncon]
                        )
                    ]
                    n['transitions'] += [
                        ['advance', 'BASE', subname,
                         cond + [ncon] if cond else [ncon]],
                        ['advance', subname, None,
                         cond + [ncon, wait] if cond else [[ncon, wait]],
                         None, None, [tick]],
                    ]

                return n

            # TODO: (redd@) Add equivalent for fix'd nest
            def flow(vals, delayed, cond: List, infl: List, react: List):
                """
                Returns a nest encapsulating a set of flow values.

                Args:
                    vals: List of flow values.
                """

                c = [value(
                    fv, cond=cond, delayed=delayed,
                    infl=infl,
                    react=react) for fv in vals] + [node(name='INIT')]
                t = [['advance', ['INIT'] + [str(src).upper() for src in vals if src != fv],
                      str(fv).upper(), cond + [lambda: sample() == fv]] for fv in vals]

                return node(
                    name='FLW',
                    children=c,
                    influences=infl,
                    reactions=react,
                    initial='INIT',
                    on_enter=[lambda _: self.advance()],
                    transitions=t,
                    conditions=cond
                )

            return node(
                name=ctrl.name.upper(),
                conditions=cond,
                reactions=react,
                children=[
                    flow(ctrl.flow_vals, ctrl.allowance > 0, cond, infl, react),
                    value('FXD', False, ctrl.latency > 0, cond, infl, react),
                    node(name='INIT')
                ],
                influences=infl,
                initial='INIT',
                on_enter=[lambda _: self.advance()],
                transitions=[
                    ['advance', ['INIT', 'FXD'], 'FLW', cond + [is_flow]],
                    ['advance', ['INIT', 'FLW'], 'FXD', cond + [is_fix]],
                ]
            )

        def add_level(bh, controls: Iterable[cis.Control]):
            """
            Appends behavior [to an existing self] corresponding to a set of controls along a
            precedence level. As defined, a set of Controls within a precedence level can be
            treated as distinct outcomes e.g. such that a single Control context can be
            explored by an interface self at a time.

            Args:
                bh: A nest representing the current behavioral hierarchy.
                controls: List of Controls representing a single precedence level.
            """

            # Control-nest's influences are all other instantiated Controls along/above its precedence level
            cond = {}
            for c in controls:
                match = next(
                    (r for r in self.reactions if r.cname == c.name and r.force),
                    None)
                if c.instantiated:
                    cond[c.name] = {}
                    cond[c.name]['fix'] = lambda: c.capture() in c.fix_vals
                    cond[c.name]['flow'] = lambda: c.capture() in c.flow_vals
                elif match is not None:
                    # Forced reactions create 'virtual' precedence levels
                    for f in flatten(get_flowers(bh)):
                        f['tags'].remove('flow')
                        f['initial'] = c.name.upper()
                        f['children'] = [
                            node(
                                name=c.name.upper(),
                                tags=['flow'],
                                influences=f['influences'],
                                conditions=f['conditions'],
                                reactions=f['reactions'] + [match.fns]
                            )
                        ]
                        f['transitions'] = []
                        f['on_enter'] = []

            # Elaborate behavior of instantiated Controls, if any
            if cond:
                for f in flatten(get_flowers(bh)):

                    f['tags'].remove('flow')
                    f['initial'] = 'INIT'
                    f['children'] = [node(name='INIT')]
                    f['on_enter'] = [lambda _: self.advance()]
                    f['transitions'] = []

                    for c in controls:
                        if c.instantiated:
                            mutex = [v['fix'] for k, v in cond.items() if k != c.name]
                            f['children'] += [
                                nestify(
                                    c,
                                    f['conditions'] + mutex,
                                    f['influences'] + cond.keys(),
                                    f['reactions']
                                )
                            ]
                            f['transitions'] += [
                                ['advance', ['INIT'] + [k.upper() for k in cond.keys() if k != c.name],
                                 c.name.upper(), mutex + [cond[c.name]['flow']]]
                            ]

        # Elaborate!
        bh = node(name='ROOT', tags=['flow'])
        controls = sorted(self.itf.controls, reverse=True)
        for k, g in itertools.groupby(controls, lambda x: x.precedence):
            add_level(bh, g)

        # TODO: (redd@) Add callback accepting event data to determine src of context violation
        bh['transitions'] += ['advance', '*', 'INIT']

        return bh

    @property
    def primary(self) -> Optional[bool]:
        return self._primary

    @primary.setter
    def primary(self, val: Optional[bool]) -> None:
        self._primary = val

    @property
    def busy(self) -> Optional[bool]:
        """
        Returns True if model is currently processing contents of `self.buff`, False if
        model is finished, and, None if model is idle.
        """
        return self._busy

    @busy.setter
    def busy(self, val: Optional[bool]) -> None:
        self._busy = val

    @property
    def buff(self) -> Dict[str, Deque]:
        return self._buff

    def _clear(self) -> None:
        [v.clear() for v in self.buff.values()]
        self.busy = None
        _LOGGER.debug(f"{str(self)} buffer cleared")

    def _input(self, txn: Dict) -> None:
        """Buffer logical input transactions."""
        if self.busy:
            raise ci.InterfaceProtocolError(f"{str(self)} cannot ingest logical input if busy")

        if txn.keys() != self.itf._txn(d=self.primary):
            raise ValueError(
                f"{str(self)} buffer expects {self.itf._txn(d=self.primary)}"
            )

        for k, v in txn.items():
            self.buff[k].extendleft(v)

        self.busy = True
        _LOGGER.debug(f"{str(self)} buffered input: {txn}")

    def _output(self) -> Dict:
        """Returns completed logical output transaction."""
        if self.busy:
            raise ci.InterfaceProtocolError(f"{str(self)} cannot flush logical output if busy")

        out = {k: list(v) for k, v in self.buff.items()}
        self._clear()
        _LOGGER.debug(f"{str(self)} buffered output: {out}")
        return out

    def _event_loop(self) -> None:
        """Main event loop for behavioral models."""
        _LOGGER.debug(f"{str(self)} looping...")
        self.advance()

        if not (self.get_state(self.state).is_flow or self.get_state(self.state).is_fix):
            raise ci.InterfaceProtocolError(f"Control context invariant was violated")

        # Delete cached values of influences, execute reactions
        for c in self.get_state(self.state)['influences']:
            getattr(self.itf, c).clear()

        for fn in self.get_state(self.state)['reactions']:
            fn()

        _LOGGER.debug(f"{str(self)} looped!")
