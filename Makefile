PYTHON ?= python

.PHONY: up seed scenario register agents verify reset demo

up seed scenario register agents verify reset demo:
	$(PYTHON) run.py $@
