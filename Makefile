.PHONY: venv lint test requirements example

check_venv = $(if $(wildcard venv),,$(error Run `make venv`))

venv:
	python3 -m venv venv
	venv/bin/pip install -r requirements/dev.txt
	venv/bin/pip install -e .

lint:
	$(check_venv)
	venv/bin/ruff check .

test:
	$(check_venv)
	venv/bin/pytest

requirements:
	$(check_venv)
	venv/bin/pip-compile-multi

example:
	$(check_venv)
	venv/bin/python example/example_parser.py --watch . example/repo/docs output