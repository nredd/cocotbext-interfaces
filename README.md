# cocotbext-interfaces

Interface abstractions for [cocotb](https://github.com/cocotb/cocotb) testbenches. Each
interface wraps the DUT's signals, validates them against the protocol's rules, and exposes
cocotb-style driver and monitor classes.

Only Avalon Streaming (Avalon-ST) is implemented. It lives in
`cocotbext.interfaces.avalon.streaming`.

Status: experimental, version `0.1.1`. The API is unstable.

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

`make install` runs the same command.

## Usage

The protocol specification is attached to the interface, and the names come from the
`bus_name` argument. With `bus_name="asi"`, the interface looks for `asi_data`, `asi_valid`,
`asi_ready` and so on.

`StreamingDriver` is the Avalon-ST source. It drives the DUT's input stream.
`StreamingMonitor` is the passive sink. It observes the DUT's output stream and passes each
completed packet or transaction to an optional `callback`.

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
setup. It adds a `cocotb` scoreboard on the sink and a `BitDriver` on `aso_ready`.

### Transactions

A transaction is a `dict`. Keys are signal names and values are lists, one entry per
transfer:

- `data`: `BinaryValue` per symbol
- `channel`: `int`, only if the `channel` signal exists
- `error`: `int`, only if the `error` signal exists

### Signal rules

Checked when the interface is constructed:

- `clk` and `reset` are required. They are not prefixed by `bus_name`.
- `reset` is always active-high. The `reset` spec hardcodes that name, so the `_n` suffix
  rule cannot change it.
- Other signals are active-high unless their name ends in `_n`, which makes them active-low.
- `data` width is 1 to 4096 bits. `channel` is 1 to 128 bits. `error` is 1 to 256 bits.
  `empty` is 1 to 5 bits.
- `startofpacket` and `endofpacket` are both required once any packet signal exists.
- `empty` is required when the data width is more than `data_bits_per_symbol`. The width check
  is meant to be `ceil(log2(symbols per word))`, but see Known issues.
- `ready_latency` must be less than or equal to `ready_allowance`.
- A missing optional signal is logged and skipped. Passing a related option without its
  signal emits a `warnings.warn` and the option is ignored.

### `StreamingInterface` options

- `data_bits_per_symbol`: 1 to 512, default 8
- `first_symbol_in_higher_order_bits`: default `True`
- `max_channel`: 0 to 255. Defaults to 0 with a warning when a `channel` signal exists
- `error_descriptor`: list of strings, one per error bit
- `empty_within_packet`: default `False` when packet signals exist
- `ready_allowance`, `ready_latency`: default 0 each
- `in_packet_timeout`: default 0 when packet signals exist

`get_descriptors(mask)` returns the descriptor strings for set error bits.
`mask_data(data, empty)` strips the empty symbols from a data word.

## Tests and examples

```
make            # runs install, then the tests under tests/
make -C tests   # tests only
```

`make` runs `bin/combine_results.py` afterward to merge JUnit XML results. The `examples/`
directory is empty.

The bundled design is `tests/designs/avalon_streaming_module/avalon_streaming.sv`. It is a
10-entry FIFO with 8-bit data.

## Known issues

- The sink path is probably broken. `PassiveSinkModel` buffers `data`, `error` and `channel`,
  but those signals are `FROM_PRIMARY`, so the sink's buffer keys come back empty and a
  `KeyError` is likely. This was found by code reading and has not been run.
- The bundled design resets while `reset` is low. The library treats `reset` as active-high.
- The `empty` width check uses `math.ceil(math.log(...), 2)`, which passes the base as the
  `ceil` argument and raises a `TypeError` when reached.
- The source does not compute or drive `empty` yet.
- `in_packet_timeout` is accepted but not enforced.
- Only the passive sink exists. There is no active sink model.
- The bundled test targets the cocotb 1.4 API (`cocotb.drivers`, `cocotb.generators`,
  `cocotb.scoreboard`). Newer cocotb releases will not run it as written.

## Attribution

This project depends on cocotb. The `LICENSE` file is cocotb's Revised BSD license text with
cocotb's copyright notices (Potential Ventures Ltd, SolarFlare Communications Inc). Keep it with
any copy of this repo. The Makefiles carry the same notices.
