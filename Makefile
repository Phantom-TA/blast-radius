ifeq ($(OS),Windows_NT)
PYTHON ?= python
else
PYTHON ?= python3
endif

.PHONY: up seed prepare scenario register rooms agents verify reset demo

up seed prepare scenario register rooms agents verify reset demo:
	$(PYTHON) run.py $@
