.PHONY: venv test format

VENV = .venv
PY = $(VENV)/bin/python

venv:
	python3 -m venv $(VENV)
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements-dev.txt

test:
	$(PY) -m pytest -q

format:
	$(PY) -m black src tests
