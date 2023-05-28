.DEFAULT_GOAL = compile

compile:
	@ ./Taskfile compile
.PHONY: compile

list:
	@ ./Taskfile modules
.PHONY: list

verify:
	@ ./Taskfile verify
.PHONY: verify

check:
	@ ./Taskfile check
.PHONY: check
