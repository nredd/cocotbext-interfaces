#!/usr/bin/env python3
"""Test to demonstrate functionality of the avalon basic streaming interface"""

import random

import cocotb as c
import cocotb.binary as cb
import cocotb.clock as cc
import cocotb.drivers as cd
import cocotb.generators as cg
import cocotb.scoreboard as cs
import cocotb.triggers as ct

import cocotbext.interfaces.avalon.streaming as cias

class AvalonSTTB(object):
    """Testbench for avalon basic stream"""
    def __init__(self, dut):
        self.dut = dut
        self.clkedge = ct.RisingEdge(dut.clk)

        self.st_source = cias.StreamingDriver(self.dut, bus_name="asi")
        self.st_sink = cias.StreamingMonitor(self.dut, bus_name="aso")
        self.scoreboard = cs.Scoreboard(self.dut, fail_immediately=True)

        self.expected_output = []
        self.scoreboard.add_interface(self.st_sink, self.expected_output)

        self.backpressure = cd.BitDriver(self.dut.aso_ready, self.dut.clk)

    @c.coroutine
    async def initialise(self):

        self.dut.aso_ready <= 1
        self.dut.asi_valid <= 0
        self.dut.asi_data <= 0
        c.fork(cc.Clock(self.dut.clk, 2).start())
        self.dut.reset <= 1
        await ct.Timer(10)
        self.dut.reset <= 0
        await ct.Timer(10)


    @c.coroutine
    async def send_data(self, data):
        self.expected_output.append(data)
        await self.st_source.send(data)
        await self.st_sink.wait_for_recv() # TODO: (redd@) timeout

@c.test()
async def test_avalon_stream(dut):
    """Test stream of avalon data"""

    tb = AvalonSTTB(dut)
    await tb.initialise()
#    tb.backpressure.start(wave()) TODO: fix bps, initialized value

    for _ in range(20):
        data = {
            'data': [
                cb.BinaryValue(value=random.randint(0,(2^7)-1))
                for _ in range(random.randint(0,100))
            ]
        }

        await tb.send_data(data)

    raise tb.scoreboard.result
