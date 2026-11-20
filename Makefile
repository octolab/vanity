.DEFAULT_GOAL = compile

compile:
	@ python3 bin/catalog.py build dist
.PHONY: compile

list:
	@ python3 bin/catalog.py manifest
.PHONY: list

validate:
	@ python3 bin/catalog.py check
.PHONY: validate

verify:
	@ python3 bin/verify.py dist
.PHONY: verify

test:
	@ python3 -m unittest discover -s bin/tests
.PHONY: test

check:
	@ ./Taskfile check
.PHONY: check
