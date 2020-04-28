TOPLEVEL_LANG ?= verilog

ifneq ($(TOPLEVEL_LANG),verilog)

all:
	@echo "Skipping test due to TOPLEVEL_LANG=$(TOPLEVEL_LANG) not being verilog"
clean::

else

TOPLEVEL := avalon_streaming

COCOTB:=$(CURDIR)/../../..

SHELL := $(COCOTB)/shell

VERILOG_SOURCES = $(COCOTB)/tests/designs/avalon_streaming_module/avalon_streaming.sv

include $(shell cocotb-config --makefiles)/Makefile.sim

endif

MODULE = test_avalon_stream