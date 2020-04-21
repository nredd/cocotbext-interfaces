#!/usr/bin/env python3
"""Test to demonstrate functionality of the avalon basic streaming interface"""

import logging
import random
import struct
import sys

import cocotb
from cocotb.drivers import BitDriver
from cocotb.drivers.avalon import AvalonST as AvalonSTDriver
from cocotb.triggers import RisingEdge, Timer
from cocotb.clock import Clock
from cocotb.scoreboard import Scoreboard
from cocotb.generators.bit import wave

import cocotbext.interfaces
#from cocotbext.interfaces.avalon.driver import AvalonST as AvalonSTDriver
from cocotbext.interfaces.avalon.monitor import AvalonST as AvalonSTMonitor

class AvalonSTTB(object):
    """Testbench for avalon basic stream"""
    def __init__(self, dut):
        self.dut = dut
        self.clkedge = RisingEdge(dut.clk)

        self.stream_in = AvalonSTDriver(self.dut, "asi", dut.clk)
        self.stream_out = AvalonSTMonitor(self.dut, bus_name="aso")
        self.scoreboard = Scoreboard(self.dut, fail_immediately=True)

        self.expected_output = []
        self.scoreboard.add_interface(self.stream_out, self.expected_output)

        self.backpressure = BitDriver(self.dut.aso_ready, self.dut.clk)

    @cocotb.coroutine
    async def initialise(self):
        self.dut.aso_valid <= 0
        self.dut.aso_ready <= 0
        self.dut.aso_data <= 0

        cocotb.fork(Clock(self.dut.clk, 2).start())
        self.dut.reset <= 1
        await Timer(10)
        self.dut.reset <= 0
        await Timer(10)

    # TODO: (redd@) Reformat scoreboards

    @cocotb.coroutine
    async def send_data(self, data):
        exp_data = struct.pack("B",data)
        self.expected_output.append(exp_data)
        await self.stream_in.send(data)

@cocotb.test(expect_fail=False)
async def test_avalon_stream(dut):
    """Test stream of avalon data"""

    tb = AvalonSTTB(dut)
    await tb.initialise()
    tb.backpressure.start(wave())

    for _ in range(20):
        data = random.randint(0,(2^7)-1)
        await tb.send_data(data)
        await tb.clkedge

    for _ in range(5):
        await tb.clkedge

    raise tb.scoreboard.result
