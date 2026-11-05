ifeq ($(OS),Windows_NT)
PYTHON ?= python
else
PYTHON ?= python3
endif

.PHONY: up seed scenario register rooms agents verify reset demo

up seed scenario register rooms agents verify reset demo:
	$(PYTHON) run.py $@
