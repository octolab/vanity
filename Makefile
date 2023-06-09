.DEFAULT_GOAL = compile

compile:
	@ ./Taskfile compile
.PHONY: compile

list:
	@ ./Taskfile modules
.PHONY: list

validate:
	@ ./Taskfile validate
.PHONY: validate

verify:
	@ ./Taskfile verify
.PHONY: verify

test:
	@ ./Taskfile tests
.PHONY: test

check:
	@ ./Taskfile check
.PHONY: check
