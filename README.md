# cocotbext-interfaces

Interface abstractions for [cocotb](https://github.com/cocotb/cocotb) testbenches. Each
interface wraps the DUT's signals, validates them against the protocol's rules, and exposes
cocotb-style driver and monitor classes.

Only Avalon Streaming (Avalon-ST) is implemented. It lives in
`cocotbext.interfaces.avalon.streaming`.

Status: experimental, version `0.1.1`. The API is unstable. See Known issues before relying on
the monitor.

## Requirements

- Python 3.7 or newer (`python_requires` in `setup.py`)
- cocotb 1.4.x. `setup.py` requests it from git (`potentialventures/cocotb@master`), so the
  install needs network access to GitHub
- `transitions[diagrams]`, installed automatically
- A simulator supported by cocotb, for the bundled tests only. The repo does not pick one

## Install

```
pip install -e .
```

Plain `make` runs the same command and nothing else.

## Usage

The protocol specification is attached to the interface, and signal names come from the
`bus_name` argument. With `bus_name="asi"`, the interface looks for `asi_data`, `asi_valid`,
`asi_ready` and so on.

`StreamingDriver` is the Avalon-ST source. It drives the DUT's input stream.
`StreamingMonitor` is the passive sink. It observes the DUT's output stream and passes each
completed packet or transaction to an optional `callback`. The sink path has a known problem,
see Known issues.

```python
import cocotb as c
from cocotb.binary import BinaryValue

import cocotbext.interfaces.avalon.streaming as cias


@c.test()
async def stream_test(dut):
    source = cias.StreamingDriver(dut, bus_name="asi")
    sink = cias.StreamingMonitor(dut, bus_name="aso")

    # Keys must match the non-meta, FROM_PRIMARY signals present on the source interface
    await source.send({'data': [BinaryValue(value=0x5A, n_bits=8)]})
    await sink.wait_for_recv()
```

The bundled test, `tests/test_cases/test_avalon_stream/test_avalon_stream.py`, shows a fuller
setup. It adds a `cocotb` scoreboard on the sink and creates a `BitDriver` on `aso_ready`,
which it never starts.

### Transactions

A transaction is a `dict`. Keys are signal names and values are lists, one entry per
transfer:

- `data`: one `BinaryValue` per transfer, as wide as the `data` signal
- `channel`: `int`, only if the `channel` signal exists
- `error`: `int`, only if the `error` signal exists

### Signal rules

Checked when the interface is constructed:

- `clk` and `reset` are required. They are not prefixed by `bus_name`. `reset_req` is optional
  and also unprefixed.
- `reset` is always active-high. The `reset` spec hardcodes that name, so the `_n` suffix
  rule cannot change it.
- At the `Signal` class level, a name ending in `_n` is active-low unless set otherwise. The
  interface adds no `_n` suffixes, so no streaming signal ends up active-low.
- `data` width is 1 to 4096 bits. `channel` is 1 to 128 bits. `error` is 1 to 256 bits.
  `empty` is 1 to 5 bits.
- `startofpacket` and `endofpacket` are both required once any packet signal exists.
- `empty` is required when the data width is more than `data_bits_per_symbol`, and the
  width check is meant to be `ceil(log2(symbols per word))`. Right now that check raises
  `TypeError` instead. See Known issues.
- `ready_latency` must be less than or equal to `ready_allowance`.
- A missing optional signal is logged and skipped. Passing a related option without its
  signal emits a `warnings.warn` and the option is ignored.

### `StreamingInterface` options

- `data_bits_per_symbol`: 1 to 512. Default 8 when a `data` signal exists
- `first_symbol_in_higher_order_bits`: default `True` when a `data` signal exists
- `max_channel`: 0 to 255. Defaults to 0 with a warning when a `channel` signal exists
- `error_descriptor`: list of strings, one per error bit
- `empty_within_packet`: default `False` when packet signals exist
- `ready_allowance`, `ready_latency`: 0 to 8. Default 0 each when a `ready` signal exists
- `in_packet_timeout`: default 0 when packet signals exist

`bus_name`, `bus_separator` (default `"_"`) and `log_level` are also accepted. `family` is not,
because the Avalon base class sets it and passing it again raises `TypeError`.

`get_descriptors(mask)` returns the descriptor strings for set error bits.
`mask_data(data, empty)` slices `empty` bits off the data word. It does not scale by symbol
width, see Known issues.

## Tests and examples

```
make test       # install, tests/ and examples/, then bin/combine_results.py
make -C tests   # tests only
```

`make test` needs a working simulator and cocotb. Without them, `tests/Makefile` calls
`cocotb-config` at parse time, so it must be on `PATH`.

`bin/combine_results.py` merges JUnit XML results. The `examples/` directory has only a
Makefile and no examples.

The bundled design is `tests/designs/avalon_streaming_module/avalon_streaming.sv`. It is a
10-entry FIFO with 8-bit data.

## Known issues

- The sink path is probably broken. `PassiveSinkModel` buffers `data`, `error` and `channel`,
  but those signals are `FROM_PRIMARY`, so the sink's buffer keys come back empty and a
  `KeyError` is likely. This was found by code reading and has not been run.
- Packet interfaces with data wider than one symbol raise `TypeError` in the `empty` width
  check, because `math.ceil(math.log(...), 2)` passes the base as the second argument. That
  makes the "`empty` required" error unreachable.
- `mask_data` slices `empty` bits, not `empty * data_bits_per_symbol`. With big-endian data and
  `empty` of 0 it returns an empty string.
- `max_channel` is validated at construction, but the per-transfer range check in the sink is
  commented out.
- The bundled design resets while `reset` is low. The library treats `reset` as active-high.
- The source does not compute or drive `empty` yet.
- `in_packet_timeout` is accepted but not enforced.
- Only the passive sink exists. There is no active sink model.
- The bundled test targets the cocotb 1.4 API (`cocotb.drivers`, `cocotb.generators`,
  `cocotb.scoreboard`). Newer cocotb releases will not run it as written.

## Attribution

This project depends on cocotb. The `LICENSE` file is cocotb's Revised BSD license text with
cocotb's copyright notices (Potential Ventures Ltd, SolarFlare Communications Inc). Keep it with
any copy of this repo. The Makefiles carry the same notices.
