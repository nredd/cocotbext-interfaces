import abc
import collections
import inspect
import itertools
import logging
from typing import List, Optional, Set, Dict, Iterable, Callable, Deque, Awaitable

import cocotb as c
import transitions as t
import transitions.extensions as te
import transitions.extensions.nesting as ten
import transitions.extensions.states as tes
from cocotb.triggers import ReadOnly, Event, NextTimeStep

import cocotbext.interfaces as ci

class Behavioral(ten.State):
    """
    Collects attributes associated with a given `State`, as needed for behavioral modelling.

    Attributes:
        conditions: List of boolean conditions which constrain `Control`s to a specific value,
        used to define behavioral context.
        reactions: List of behaviorally-inherited reactions.
        influences: List of `Control`s whose values must be known while in a given `State`,
        used to determine which `Control`s must be re-sampled after completing a cycle.
    """


    @property
    def conditions(self) -> List: return self._conditions
    @property
    def reactions(self) -> List: return self._reactions
    @property
    def influences(self) -> List: return self._influences


    def __init__(self, *args, **kwargs):
        """
        Args:
            **kwargs: If kwargs contains `volatile`, always create an instance of the passed class
                whenever the state is entered. The instance is assigned to a model attribute which
                can be passed with the kwargs keyword `hook`. If hook is not passed, the instance will
                be assigned to the 'attribute' scope. If `volatile` is not passed, an empty object will
                be assigned to the model's hook.
        """
        self._conditions = kwargs.pop('conditions', [])
        self._reactions = kwargs.pop('reactions', [])
        self._influences = kwargs.pop('influences', [])
        super().__init__(*args, **kwargs)
        self.initialized = True

    # TODO: (redd@) Anything fun to add here?


@tes.add_state_features(tes.Tags, tes.Volatile, Behavioral)
class BaseModel(te.HierarchicalMachine, ci.Pretty, metaclass=abc.ABCMeta): # TODO: (redd@) Get GraphMachine working
    # TODO: (redd@) refactor w/ AsyncMachine + async primitives? would improve performance


    @property
    def itf(self) -> ci.core.BaseInterface:
        return self._itf

    @property
    def reactions(self) -> Set[Callable]:
        return self._reactions




    @property
    def primary(self) -> Optional[bool]:
        return self._primary

    @primary.setter
    def primary(self, val: Optional[bool]) -> None:
        self._primary = val

    @property
    def busy(self) -> bool:
        """
        Returns True if model is currently processing contents of `self.buff`, False if
        model is finished, and, None if model is idle.
        """
        return self._busy

    @busy.setter
    def busy(self, val: bool) -> None:
        self._busy = val

    @property
    def buff(self) -> Dict[str, Deque]:
        return self._buff

    @property
    def nchunks(self) -> int: return max(len(d) for d in self.buff.values()) if self.buff else 0


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

        def nestify(ctrl: ci.signal.Control, cond: List, infl: List, react: List) -> Dict:
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
                pcon = lambda : sample() == val
                ncon = lambda : sample() != val

                # Include reaction if defined
                match = next(
                    (r for r in self.reactions if r.cname == ctrl.name and r.val == val), None
                )
                react = ([] if react is None else react) + ([] if match is None else [match])
                cond = cond + [pcon] if cond else [pcon]

                n = node(
                    name=str(val).upper(),
                    tags=['flow' if flow else 'fix'],
                    conditions=cond,
                    influences=infl,
                    reactions=react
                )

                # TODO: (redd@) Fix: initial + transitioning logic when entering latency
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

            def fix(vals, delayed, cond: List, infl: List, react: List):
                """
                Returns a nest encapsulating a set of fix values.

                Args:
                    vals: List of fix values.
                """

                c = [value(fv, flow=False, cond=cond, delayed=delayed,
                           infl=infl, react=react) for fv in vals] + [node(name='INIT')]
                t = [{'trigger': 'advance',
                      'source': ['INIT'] + [str(src).upper() for src in vals if src != fv],
                      'dest': str(fv).upper(),
                      'conditions': cond + [lambda: sample() == fv]
                      } for fv in vals]

                return node(
                    name='FXD',
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
                    flow(ctrl.flow_vals, ctrl.allowance > 0, cond=cond, infl=infl, react=react),
                    fix(ctrl.fix_vals, ctrl.latency > 0, cond=cond, infl=infl, react=react),
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

            self.log.debug(f"New control-nest: {n}")
            return n

        def add_level(bh, controls: Iterable[ci.signal.Control]):
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
                self.log.debug(f"{self} preprocessing: {str(c)}")
                match = next((r for r in self.reactions if r.cname == c.name and r.force), None)
                if c.instantiated:
                    cond[c.name] = {
                        'obj': c,
                        'fix': lambda: c.capture() in c.fix_vals,
                        'flow': lambda: c.capture() in c.flow_vals
                    }
                elif match is not None: # Forced reactions create 'virtual' precedence levels
                    self.log.debug(f"{self} inserting forced reaction: {str(match)}")
                    for f in flatten(get_flowers(bh)):
                        f['tags'].remove('flow')
                        f['initial'] = c.name.upper()
                        f['children'] = [
                            node(
                                name=c.name.upper(),
                                tags=['flow'],
                                influences=f['influences'],
                                conditions=f['conditions'],
                                reactions=f['reactions'] + [match]
                            )
                        ]
                        f['transitions'] = []
                        f['on_enter'] = []

            if cond: # Elaborate behavior of instantiated Controls, if any
                for f in flatten(get_flowers(bh)):
                    self.log.debug(f"{self} adding to flower ({f})")
                    f['tags'].remove('flow')
                    f['transitions'] = []

                    if len(cond.keys()) > 1:

                        f['on_enter'] = [lambda : self.trigger('advance')]
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
                                 'source': [k.upper() for k in cond.keys() if k != key],
                                 'dest': key.upper(),
                                 'conditions': mutex}
                            )
                    else:
                        match = next(iter(cond))
                        f['initial'] = match.upper()
                        f['children'].append(
                            nestify(
                                cond[match]['obj'],
                                f['conditions'],
                                f['influences'] + [match],
                                f['reactions']
                            )
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

    def _flush(self) -> Dict[str, List]:
        out = {k: list(v) for k,v in self.buff.items()}
        [d.clear() for d in self.buff.values()]
        self.log.debug(f"{self} buffer flushed: {out}")
        return out

    def _load(self, txn: Dict[str, Iterable]) -> None:
        for k, v in txn.items():
            self.buff[k].extendleft(v)
        self.log.debug(f"{self} loaded buffer ({txn})")


    @c.coroutine
    async def acquire(self):
        if self.busy:
            await self.busy_event.wait()
        self.busy_event.clear()
        self.busy = True

    def release(self):
        self.busy = False
        self.busy_event.set()

    @c.coroutine
    async def input(self, txn: Dict[str, Iterable], trig: Awaitable) -> None:
        """Blocking call to ingest a[n input] logical transaction."""

        if set(txn.keys()) != self.itf._txn(primary=self.primary):
            raise ValueError(
                f"{self} expects input format: {str(self.itf._txn(primary=self.primary))}"
            )

        await self.acquire()
        self._load(txn)

        while self.busy:
            await trig
            await self._event_loop()

        self._flush() # Make sure buffer is empty

        self.log.info(f"{self} completed input")

    @c.coroutine
    async def output(self, trig: Awaitable) -> Dict:
        """
        Blocking call to sample simulation stimuli and process (return) the corresponding
        [output] logical transaction.
        """

        await self.acquire()

        while self.busy:
            await trig
            await self._event_loop()

        txn = self._flush()
        self.log.info(f"{self} completed output")
        return txn

    @c.coroutine
    async def _event_loop(self) -> None:
        """
        Main event loop for behavioral models.
        """
        # TODO: (redd@) clean
        # TODO: (redd@) Could use cocotb Events to standardize waiting; don't block until a reaction is available?
        self.log.debug(f"{self} looping...")

        await ReadOnly() # Need all signals stabilized while model transitions
        self.trigger('advance')

        # TODO: (redd@) Reimplement to consider source (shouldn't error out in beginning of sim w/ lots of undefined signals)
        if self.state == 'TOP_NULL':
            raise ci.InterfaceProtocolError(f"Control context invariant was violated")

        # Delete cached values of influences, execute reactions TODO (redd@): revisit
        # for c in self.get_state(self.state).influences:
        #     self.itf[c].clear()

        for fn in self.get_state(self.state).reactions:
            if fn.smode != ReadOnly:
                await NextTimeStep()
                await fn.smode()

            fn(self) # TODO: (redd@) fix method binding

        self.log.debug(f"{self} looped!")


    @abc.abstractmethod
    def __init__(self, itf: ci.core.BaseInterface, primary: Optional[bool] = None) -> None:
        """Should be extended by child class."""

        ci.Pretty.__init__(self) # Logging

        t.core._LOGGER = self.log
        ten._LOGGER = self.log
        tes._LOGGER = self.log

        self._itf = itf

        self.busy = False
        self.busy_event = Event(f"{self.__class__.__name__}_busy")

        self._primary = primary
        self._buff = {k: collections.deque() for k in self.itf._txn(primary=self.primary)}
        self._reactions = set(
            d[1].__func__ for d in inspect.getmembers(self, predicate=inspect.ismethod)
            if getattr(d[1].__func__, 'reaction', False)
        )
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
        self.log.debug(f"New {self}")
