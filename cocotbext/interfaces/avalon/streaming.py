import abc

import math

import warnings
from typing import List, Optional, Set, Callable

import cocotb.triggers as ct

import cocotbext.interfaces as ci
import cocotbext.interfaces.avalon as cia
from cocotb.binary import BinaryValue

class StreamingInterface(cia.BaseSynchronousInterface):

    @classmethod
    def specification(cls) -> Set[ci.signal.Signal]:
        return {
            ci.signal.Signal('channel', widths={x + 1 for x in range(128)}, logical_type=int),
            ci.signal.Signal(
                'data',
                widths={x + 1 for x in range(4096)},
                logical_type=BinaryValue
            ),
            ci.signal.Signal('error', widths={x + 1 for x in range(256)}, logical_type=int),
            ci.signal.Signal('empty', widths={x + 1 for x in range(5)}, meta=True, logical_type=int),
            ci.signal.Signal('endofpacket', meta=True),
            ci.signal.Signal('startofpacket', meta=True),
            ci.signal.Control('ready', direction=ci.signal.Direction.TO_PRIMARY, max_allowance=8, max_latency=8),
            ci.signal.Control('valid', precedence=1),
        }

    def __init__(self, *args,
                 data_bits_per_symbol: Optional[int] = None,
                 empty_within_packet: Optional[bool] = None,
                 error_descriptor: Optional[List[str]] = None,
                 first_symbol_in_higher_order_bits: Optional[bool] = None,
                 max_channel: Optional[int] = None,
                 ready_latency: Optional[int] = None,
                 ready_allowance: Optional[int] = None,
                 in_packet_timeout: Optional[int] = None,
                 **kwargs) -> None:

        super().__init__(*args, **kwargs)

        # TODO: (redd@) Add ready, valid controllers
        # TODO: (redd@) Drive defaults to each signal
        # TODO: (redd@) Log properties below
        # TODO: (redd@) Add, implement use_empty attribute
        # If any packet signals defined, assume packet support
        self._packets = self['empty'].instantiated or \
                        self['startofpacket'].instantiated or \
                        self['endofpacket'].instantiated

        if self['channel'].instantiated:
            if max_channel is None:
                warnings.warn(
                    f"Channel signal instantiated without providing maxChannel, "
                    f"so default of 0 will be used--is this intended?"
                )
                self._max_channel = 0
            elif not 255 >= max_channel >= 0:
                raise ci.InterfacePropertyError(
                    f"AvalonST spec defines maxChannel as 0-255. "
                    f"{str(self)} maxChannel is {max_channel}"
                )
            else:
                self._max_channel = max_channel
        else:
            if max_channel is not None:
                warnings.warn(
                    f"maxChannel cannot be set without instantiated Channel signal"
                )
            self._max_channel = None

        if self['data'].instantiated:
            if data_bits_per_symbol is None:
                self._data_bits_per_symbol = 8
            elif not 512 >= data_bits_per_symbol >= 1:
                raise ci.InterfacePropertyError(
                    f"AvalonST spec defines dataBitsPerSymbol as 1-512. "
                    f"{str(self)} dataBitsPerSymbol is {data_bits_per_symbol}"
                )
            else:
                self._data_bits_per_symbol = data_bits_per_symbol

            if first_symbol_in_higher_order_bits is None:
                self._first_symbol_in_higher_order_bits = True
            else:
                self._first_symbol_in_higher_order_bits = first_symbol_in_higher_order_bits
        else:
            if data_bits_per_symbol is not None:
                warnings.warn(f"dataBitsPerSymbol cannot be set without instantiated Data signal")
            if first_symbol_in_higher_order_bits is not None:
                warnings.warn(f"firstSymbolInHighOrderBits provided without instantiated Data signal")

        if self['error'].instantiated:
            if error_descriptor is None:
                self._error_descriptor = None
            elif len(self['error'].handle) != len(error_descriptor):
                raise ci.InterfacePropertyError(
                    f"AvalonST spec requires that error descriptors "
                    f"be provided as list of strings, one for each error bit. "
                    f"{str(self)} provided {error_descriptor}"
                )
            else:
                self._error_descriptor = error_descriptor
        else:
            if error_descriptor is not None:
                warnings.warn(f"errorDescriptor provided without instantiated Error signal")
            self._error_descriptor = None

        if self['ready'].instantiated:
            if ready_allowance is None:
                self._ready_allowance = 0
            else:
                self._ready_allowance = ready_allowance

            if ready_latency is None:
                self._ready_latency = 0
            else:
                self._ready_latency = ready_latency

            if self.ready_latency > self.ready_allowance:
                raise ci.InterfacePropertyError(
                    f"AvalonST spec requires readyLatency <= readyAllowance. "
                    f"{str(self)} readyLatency is {self.ready_latency}, "
                    f"readyAllowance is {self.ready_latency}"
                )
            self['ready'].allowance = self.ready_allowance
            self['ready'].latency = self.ready_latency
        else:
            if ready_latency is not None:
                warnings.warn(f"readyLatency provided without instantiated ready signal")
            if ready_allowance is not None:
                warnings.warn(f"readyAllowance provided without instantiated ready signal")
            self._ready_allowance = None
            self._ready_latency = None

        if self.packets:
            if in_packet_timeout is None:
                self._in_packet_timeout = 0
            elif in_packet_timeout < 0:
                raise ci.InterfacePropertyError(
                    f"In-packet timeout cannot be negative"
                )
            else:
                self._in_packet_timeout = in_packet_timeout

            if not (self['startofpacket'].instantiated and self['endofpacket'].instantiated):
                raise ci.InterfacePropertyError(
                    f"AvalonST spec requires both startofpacket and endofpacket signals"
                    f" to support packets."
                )

            # If more than one symbol per word, empty signal required
            if len(self['data'].handle) > self.data_bits_per_symbol:
                req_size = math.ceil(math.log(len(self['data'].handle) / self.data_bits_per_symbol), 2)

                if not self['empty'].instantiated:
                    raise ci.InterfacePropertyError(
                        f"AvalonST spec requires empty signal for packet interfaces "
                        f"with more than one symbol per word."
                    )

                if len(self['empty'].handle) != req_size:
                    raise ci.InterfacePropertyError(
                        f"AvalonST spec defines empty width as ceil[log_2(<symbols per cycle>)] "
                        f"= {req_size}. {str(self)} empty width is {len(self['empty'].handle)}"
                    )

            if empty_within_packet is None:
                self._empty_within_packet = False
            else:
                self._empty_within_packet = empty_within_packet
        else:
            if in_packet_timeout is not None:
                warnings.warn(f"In-packet timeout set without packet support")
            if empty_within_packet is not None:
                warnings.warn(f"emptyWithinPacket set without packet support")
            self._in_packet_timeout = None
            self._empty_within_packet = None

    def get_descriptors(self, mask: int) -> Optional[List[str]]:
        """Return list of descriptors specified by error mask, if defined."""
        if self.error_descriptor:
            ed = self.error_descriptor
            return [ed[i] for i in range(len(ed)) if mask & 2 ** i]
        return None

    def mask_data(self, data: BinaryValue, empty: int) -> BinaryValue:
        """Returns data signal masked according to empty signal. """
        be = self.first_symbol_in_higher_order_bits
        vec = BinaryValue(bigEndian=be)
        val = data.value.binstr[:-empty] if be else data.value.binstr[empty:]
        vec.assign(val)
        if not vec.is_resolvable:
            raise ci.InterfaceProtocolError(f"Signal ({str(self['data'])} is unresolvable.")
        return vec

    @property
    def packets(self) -> bool:
        return self._packets

    @property
    def data_bits_per_symbol(self) -> Optional[int]:
        return self._data_bits_per_symbol

    @property
    def empty_within_packet(self) -> Optional[bool]:
        return self._empty_within_packet

    @property
    def error_descriptor(self) -> Optional[List[str]]:
        return self._error_descriptor

    @property
    def first_symbol_in_higher_order_bits(self) -> Optional[bool]:
        return self._first_symbol_in_higher_order_bits

    @property
    def max_channel(self) -> Optional[int]:
        return self._max_channel

    @property
    def ready_allowance(self) -> Optional[int]:
        return self._ready_allowance

    @property
    def ready_latency(self) -> Optional[int]:
        return self._ready_latency

    @property
    def in_packet_timeout(self) -> Optional[int]:
        return self._in_packet_timeout


class BaseStreamingModel(cia.BaseSynchronousModel, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def __init__(self, itf: StreamingInterface, *args, **kwargs) -> None:

        # TODO: (redd@) Add in_packet_timeout logic
        self.in_pkt = False if itf.packets else None
        super().__init__(itf, *args, **kwargs)

    @property
    def itf(self) -> StreamingInterface: return self._itf

    @ci.decorators.reaction('reset', True)
    def reset(self):
        self.in_pkt = False if self.itf.packets else None


# TODO: (redd@) Add ActiveSinkModel
class PassiveSinkModel(BaseStreamingModel):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, primary=False, **kwargs)
        self.prev_channel = None

    @ci.decorators.reaction('reset', True)
    def reset(self):
        self.log.debug(f"{str(self)} in reset")
        self.prev_channel = None

    # TODO: (redd@) Rewrite w filters
    @ci.decorators.reaction('valid', True, force=True)
    def valid_cycle(self) -> None:

        self.log.debug(f"{str(self)} in valid_cycle")
        channel = self.itf['channel'].capture() if self.itf['channel'].instantiated else None
        data = self.itf['data'].capture() if self.itf['data'].instantiated else None
        empty = self.itf['empty'].capture() if self.itf['empty'].instantiated else None
        error = self.itf['error'].capture() if self.itf['error'].instantiated else None
        sop = self.itf['startofpacket'].capture() if self.itf['startofpacket'].instantiated else None
        eop = self.itf['endofpacket'].capture() if self.itf['endofpacket'].instantiated else None

        # Packet signal checks
        if self.itf.packets:
            if sop:
                if self.in_pkt:
                    raise ci.InterfaceProtocolError(
                        f"Duplicate startofpacket signal ({str(self.itf['startofpacket'])})"
                    )

                self.in_pkt = True

            if not self.in_pkt:
                raise ci.InterfaceProtocolError(f"Attempted transfer outside of packet")

            if self.prev_channel is not None and channel != self.prev_channel:
                raise ci.InterfaceProtocolError(
                    f"Channel changed within packet ({self.prev_channel}->{channel})"
                )

        self.prev_channel = channel
        #     if not self._properties['maxChannel'] >= channel.integer >= 0:
        #         raise ProtocolError(
        #             f"Channel ({channel.integer}) out of valid range "
        #             f"({0}-{self._properties['maxChannel']})"
        #         )

        if data is not None:
            # Apply empty signal if supported
            if self.in_pkt and (self.itf.empty_within_packet or eop):
                data = self.itf.mask_data(data, empty)
            self.buff['data'].append(data)

        if error is not None:
            self.buff['error'].append(error)

        # Transaction completed
        if not self.itf.packets or eop:

            if self.prev_channel is not None:
                self.buff['channel'].append(self.prev_channel)

            self.busy = False


class StreamingMonitor(ci.adapters.BaseMonitor):

    def __init__(self, *args, callback: Optional[Callable] = None, **kwargs) -> None:
        """Implementation for AvalonST."""

        # Args target Interface instance
        itf = StreamingInterface(*args, **kwargs)
        mod = PassiveSinkModel(itf)
        super().__init__(mod, callback)


class SourceModel(BaseStreamingModel):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, primary=True, **kwargs)

    # TODO: (redd@) Rewrite w filters

    @ci.decorators.reaction('valid', False, smode=ct.NextTimeStep)
    def assert_valid(self) -> None:
        self.log.debug(f"{str(self)} in assert_valid cycle")

        # Unforced reaction, so must manually assert valid if not generated
        if not self.itf['valid'].generated:
            self.itf['valid'].drive(True)
        if self.in_pkt is not None and max(len(b) for b in self.buff.values()) > 0:
            self.itf['startofpacket'].drive(True)

    @ci.decorators.reaction('valid', True, force=True, smode=ct.NextTimeStep)
    def valid_cycle(self) -> None:
        self.log.debug(f"{str(self)} in valid cycle")

        channel = self.buff['channel'][-1] if self.itf['channel'].instantiated else None
        data = self.buff['data'].pop() if self.itf['data'].instantiated else None
        error = self.buff['error'].pop() if self.itf['error'].instantiated else None
        # TODO: (redd@) calculate+drive empty

        remaining = max(len(b) for b in self.buff.values())

        if channel is not None:
            self.itf['channel'].drive(channel)
        if data is not None:
            self.itf['data'].drive(data)
        if error is not None:
            self.itf['error'].drive(error)

        if self.in_pkt:
            self.itf['startofpacket'].drive(False)
            if remaining == 1:
                self.itf['endofpacket'].drive(True)

        if remaining:
            if self.itf['valid'].instantiated and not self.itf['valid'].generated:
                self.itf['valid'].drive(True)
        else:
            if self.itf['valid'].instantiated and not self.itf['valid'].generated:
                self.itf['valid'].drive(False)
            self.busy = False

class StreamingDriver(ci.adapters.BaseDriver):

    def __init__(self, *args, **kwargs) -> None:
        """Implementation for AvalonST."""

        # Args target Interface instance
        itf = StreamingInterface(*args, **kwargs)
        mod = SourceModel(itf)
        super().__init__(mod)


