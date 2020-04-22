import abc
import copy
import functools
import itertools
import logging
import sys
from collections import deque
from typing import List, Optional, Set, Dict, Iterable, Callable, Deque

import transitions
from cocotb.log import SimLog
from transitions import State
from transitions.extensions import HierarchicalGraphMachine
from transitions.extensions.states import add_state_features, Tags, Volatile

import cocotbext.interfaces as ci
import cocotbext.interfaces.decorators as cid
import cocotbext.interfaces.signal as cis

# TODO: (redd@) Refactor logger configs
_LOG = SimLog(f"cocotbext.interfaces.model")
transitions.core._LOGGER.setLevel(logging.WARNING)
transitions.core._LOGGER.addHandler(logging.StreamHandler(sys.stdout))


class Behavioral(State):
    """
    Collects attributes associated with a given `State`, as needed for behavioral modelling.

    Attributes:
        conditions: List of boolean conditions which constrain `Control`s to a specific value,
        used to define behavioral context.
        reactions: List of behaviorally-inherited reactions.
        influences: List of `Control`s whose values must be known while in a given `State`,
        used to determine which `Control`s must be re-sampled after completing a cycle.
    """

    def __init__(self, *args, **kwargs):
        """
        Args:
            **kwargs: If kwargs contains `volatile`, always create an instance of the passed class
                whenever the state is entered. The instance is assigned to a model attribute which
                can be passed with the kwargs keyword `hook`. If hook is not passed, the instance will
                be assigned to the 'attribute' scope. If `volatile` is not passed, an empty object will
                be assigned to the model's hook.
        """
        self.conditions = kwargs.pop('conditions', [])
        self.reactions = kwargs.pop('reactions', [])
        self.influences = kwargs.pop('influences', [])
        super().__init__(*args, **kwargs)
        self.initialized = True

    # TODO: (redd@) Anything fun to add here?


@add_state_features(Tags, Volatile, Behavioral)
class BaseModel(HierarchicalGraphMachine, metaclass=abc.ABCMeta):
    # TODO: (redd@) refactor w/ AsyncMachine + async primitives? would improve performance

    def __str__(self):
        return f"<{str(self.itf)}-{self.__class__.__name__}>"

    def __repr__(self):
        return f"<{self.__class__.__name__}(itf={str(self.itf)},primary={self.primary}," \
               f"reactions={repr(self.reactions)}, nest={self._elaborated.items()})>"

    @abc.abstractmethod
    def __init__(self, itf: ci.BaseInterface, primary: Optional[bool] = None) -> None:
        """Should be extended by child class."""

        self._reactions = set()
        self._itf = itf

        self.busy = None
        self._primary = primary
        self._buff = {k: deque() for k in self.itf._txn(primary=self.primary)}

        self._elaborated = self._elaborate()

        # TODO: (redd@) Get send_event working
        super().__init__(
            states=self._elaborated,
            initial='TOP',
            queued=True,
        #    send_event=True,
        )

        # TODO: (redd@) make this prettier; default file location?
        # self.get_graph().draw('my_state_diagram.png', prog='dot')
        _LOG.info(f"New {repr(self)}")

    @property
    def itf(self) -> ci.BaseInterface:
        return self._itf

    @property
    def reactions(self) -> Set[cid.reaction]:
        return self._reactions

    def _add_reaction(self, val: cid.reaction) -> None:
        if any(r.cname == val.cname and r.force and val.force for r in self.reactions):
            raise ValueError(f"At most one control value reaction may be forced")
        if val in self.reactions:
            next(iter(self.reactions)).fns.extend(val.fns)
        else:
            self.reactions.add(val)
        _LOG.info(f"{str(self)} applied: {repr(val)}")


    # TODO: (redd@) cache this after init
    # TODO: (redd@) Consider generated Controls wrt influences st only generated caches deleted
    def _elaborate(self) -> Dict:
        """
        Generate states, transitions for behavioral interface model based on `itf.controls`.
        """

        # Tags:
        # flow - Denotes an accepted non-idle/operational (leaf) state
        # fix - Denotes an accepted idle/non-operational (leaf) state
        # wait - Denotes a temporary state
        # Lack of flow, fix tag indicates a non-accepted superstate; may have accepted children

        # Nested delay (volatile) states are allowed given that a parent control context persists

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

        def is_flow(state: Dict) -> bool:
            return 'tags' in state.keys() and 'flow' in state['tags']

        def is_fix(state: Dict) -> bool:
            return 'tags' in state.keys() and 'fix' in state['tags']

        def is_leaf(state: Dict) -> bool:
            return not ('children' in state.keys() and state['children'])

        def get_flowers(nest: Dict) -> List:
            if not is_fix(nest):
                if is_leaf(nest) and is_flow(nest):
                    return [nest]
                return [get_flowers(c) for c in nest['children']]

        def flatten(ls: List) -> List[Dict]:
            f = []
            for i in ls:
                if isinstance(i, list):
                    f.extend(flatten(i))
                elif i is not None:
                    f.append(i)
            return f

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
            is_fix = lambda : sample() in ctrl.fix_vals
            is_flow = lambda : sample() in ctrl.flow_vals

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
                pcon = lambda : sample() == val if flow else is_fix
                ncon = lambda : sample() != val if flow else is_flow

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
                        {'trigger': 'advance', 'source': 'BASE', 'dest': None,
                         'conditions': cond + [pcon] if cond else [pcon],
                         }
                    ]
                )

                if delayed:
                    subname = 'ALLOWANCE' if flow else 'LATENCY'
                    hook = f"{ctrl.name}_{subname.lower()}_count"

                    wait = lambda : (ctrl.allowance if flow else ctrl.latency) > getattr(self, hook)
                    tick = lambda : setattr(self, hook, getattr(self, hook) + 1)

                    n['children'].append(
                        node(
                            name=subname,
                            tags=['flow' if flow else 'fix', 'wait'],
                            volatile=int,
                            hook=hook,
                            influences=infl,
                            reactions=react,
                            conditions=cond + [ncon] if cond else [ncon]
                        )
                    )
                    n['transitions'].extend([
                        {'trigger': 'advance', 'source': 'BASE', 'dest': subname,
                         'conditions': cond + [ncon] if cond else [ncon]
                         },
                        {'trigger': 'advance', 'source': subname, 'dest': None,
                         'conditions': cond + [ncon, wait] if cond else [ncon, wait],
                         'after': [tick]}
                    ])

                return n

            def flow(vals, delayed, cond: List, infl: List, react: List):
                """
                Returns a nest encapsulating a set of flow values.

                Args:
                    vals: List of flow values.
                """

                c = [value(fv, cond=cond, delayed=delayed,
                    infl=infl, react=react) for fv in vals] + [node(name='INIT')]
                t = [{'trigger': 'advance',
                      'source': ['INIT'] + [str(src).upper() for src in vals if src != fv],
                      'dest': str(fv).upper(),
                      'conditions': cond + [lambda: sample() == fv]
                      } for fv in vals]

                return node(
                    name='FLW',
                    children=c,
                    influences=infl,
                    reactions=react,
                    initial='INIT',
                    on_enter=[lambda : self.trigger('advance')],
                    transitions=t,
                    conditions=cond
                )

            n = node(
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
                on_enter=[lambda : self.trigger('advance')],
                transitions=[
                    {'trigger': 'advance', 'source': ['INIT', 'FXD'], 'dest': 'FLW',
                     'conditions': cond + [is_flow]},
                    {'trigger': 'advance', 'source': ['INIT', 'FLW'], 'dest': 'FXD',
                     'conditions': cond + [is_fix]}
                ]
            )

            _LOG.debug(f"New control-nest: {n}")
            return n

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
                _LOG.debug(f"{str(self)} preprocessing: {str(c)}")
                match = next(
                    (r for r in self.reactions if r.cname == c.name and r.force),
                    None)
                if c.instantiated:
                    cond[c.name] = {
                        'obj': c,
                        'fix': lambda: c.capture() in c.fix_vals,
                        'flow': lambda: c.capture() in c.flow_vals
                    }
                elif match is not None: # Forced reactions create 'virtual' precedence levels
                    _LOG.debug(f"{str(self)} inserting forced reaction: {repr(match)}")
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

            if cond: # Elaborate behavior of instantiated Controls, if any
                for f in flatten(get_flowers(bh)):
                    _LOG.debug(f"{str(self)} adding to flower ({f})")
                    f['tags'].remove('flow')
                    f['initial'] = 'INIT'
                    f['children'] = [node(name='INIT')]
                    f['on_enter'] = [lambda : self.trigger('advance')]
                    f['transitions'] = []

                    for key, val in cond.items():
                        mutex = [v['fix'] for k, v in cond.items() if k != key]
                        f['children'].append(
                            nestify(
                                val['obj'],
                                f['conditions'] + mutex,
                                f['influences'] + list(cond.keys()),
                                f['reactions']
                            )
                        )
                        f['transitions'].append(
                            {'trigger': 'advance',
                             'source': ['INIT'] + [k.upper() for k in cond.keys() if k != key],
                             'dest': key.upper(),
                             'conditions': mutex + [val['flow']]}
                        )

        # Elaborate!
        bh = node(name='ROOT', tags=['flow'])
        controls = sorted(self.itf.controls)
        for k, g in itertools.groupby(controls, lambda x: x.precedence):
            add_level(bh, g)

        # TODO: (redd@) Add callback accepting event data to determine src of context violation
        # Top-level wrapper which allows proper machine initialization
        return node(
            name='TOP',
            children=[node(name='NULL', tags=['fix']), bh],
            initial='NULL',
            transitions=[
                {'trigger': 'advance', 'source': 'NULL', 'dest': 'ROOT'},
                {'trigger': 'advance', 'source': 'ROOT', 'dest': 'NULL'}
            ]
        )


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

    # TODO: (redd@) Add 'remaining_chunks' or equiv method to determine remaining busy cycles

    def _clear(self) -> None:
        [v.clear() for v in self.buff.values()]
        self.busy = None
        _LOG.debug(f"{str(self)} buffer cleared")

    def _input(self, txn: Dict[str, Iterable]) -> None:
        """Buffer logical input transactions."""
        if self.busy:
            raise ci.InterfaceProtocolError(f"{str(self)} cannot ingest logical input if busy")

        if set(txn.keys()) != self.itf._txn(primary=self.primary):
            raise ValueError(
                f"{str(self)} buffer expects {str(self.itf._txn(primary=self.primary))}"
            )

        for k, v in txn.items():
            self.buff[k].extendleft(v)

        self.busy = True
        _LOG.debug(f"{str(self)} buffered input: {txn}")

    def _output(self) -> Dict:
        """Returns completed logical output transaction."""
        if self.busy:
            raise ci.InterfaceProtocolError(f"{str(self)} cannot flush logical output if busy")

        out = {k: list(v) for k, v in self.buff.items()}
        self._clear()
        _LOG.debug(f"{str(self)} buffered output: {out}")
        return out

    def _event_loop(self) -> None:
        """Main event loop for behavioral models."""
        _LOG.debug(f"{str(self)} looping...")
        self.trigger('advance')

        if self.state == 'TOP_NULL':
            raise ci.InterfaceProtocolError(f"Control context invariant was violated")

        # Delete cached values of influences, execute reactions
        for c in self.get_state(self.state).influences:
            self.itf[c].clear()

        for fn in self.get_state(self.state).reactions:
            fn()

        _LOG.debug(f"{str(self)} looped!")
