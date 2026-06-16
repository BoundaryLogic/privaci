.PHONY: fixtures-generate fixtures-verify eval-up eval-down docs-generate docs-serve docs-build

FIXTURE_OUT := tests/fixtures/sql/demo-corp

fixtures-generate:
	python -m tests.fixtures.demo_corp.generate --tier mini --out $(FIXTURE_OUT)

# Generate into a private mktemp dir (avoids predictable /tmp symlink attacks)
# and always clean up, preserving diff's exit status as the recipe result.
fixtures-verify:
	@tmp="$$(mktemp -d)"; \
	python -m tests.fixtures.demo_corp.generate --tier mini --out "$$tmp"; \
	diff -ru $(FIXTURE_OUT) "$$tmp"; status=$$?; \
	rm -rf "$$tmp"; \
	exit $$status

# Evaluation compose stack — auto-detects Docker or Podman.
# Requires ANONYMIZATION_SALT (run: export ANONYMIZATION_SALT="$$(privaci gen-salt)").
eval-up:
	./scripts/eval-stack.sh up

eval-down:
	./scripts/eval-stack.sh down

docs-generate:
	python scripts/generate_docs.py

docs-serve: docs-generate
	mkdocs serve

docs-build: docs-generate
	mkdocs build --strict
