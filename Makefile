.DEFAULT_GOAL = compile

# the origin baked into the catalog page (canonical and social links); the
# delivery passes the one GitHub Pages reports
SITE_URL ?= https://go.octolab.org/

# the whole site: the catalog page laid over the import pages, verified
compile: docs
	@ python3 bin/catalog.py build dist --site docs/dist
.PHONY: compile

# the import pages and modules.yml only: no Node needed, no catalog page
pages:
	@ python3 bin/catalog.py build dist
.PHONY: pages

# the static export of the catalog page in docs/dist (npm ci first: make deps)
docs:
	@ cd docs && rm -rf dist && TARGET=static SITE_URL='$(SITE_URL)' npx --no-install next build
.PHONY: docs

deps:
	@ cd docs && npm ci --no-audit --no-fund
.PHONY: deps

list:
	@ python3 bin/catalog.py manifest
.PHONY: list

validate:
	@ python3 bin/catalog.py check
	@ python3 bin/catalog.py cards
.PHONY: validate

verify:
	@ python3 bin/verify.py dist
.PHONY: verify

test:
	@ python3 -m unittest discover -s bin/tests
.PHONY: test

# the built site at http://127.0.0.1:8040/, served the way GitHub Pages serves it
serve:
	@ python3 bin/serve.py dist
.PHONY: serve

# the go command against this build, not the live site: the root module, the
# toolkits and a package path the maintainer chose (./Taskfile resolve --all for
# every released public module)
resolve:
	@ ./Taskfile resolve
.PHONY: resolve

check:
	@ ./Taskfile check
.PHONY: check
