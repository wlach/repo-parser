.PHONY: example

example:
	uv run example/example_parser.py --watch . example/repo/docs output
