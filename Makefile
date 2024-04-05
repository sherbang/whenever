.PHONY: init
init:
	pip install -U pip setuptools-rust build twine
	pip install -e .

.PHONY: typecheck
typecheck: 
	mypy pysrc/ tests/
	pytest typesafety/

.PHONY: format
format:
	black pysrc/ tests/
	isort pysrc/ tests/
	cargo fmt

.PHONY: docs
docs:
	@touch docs/api.rst
	make -C docs/ html

.PHONY: test
test:
	pytest tests/
	cargo test

.PHONY: check-dist
check-dist:
	pip install -U build twine
	python -m build --sdist
	twine check dist/*

.PHONY: ci-lint
ci-lint: check-dist
	flake8 pysrc/ tests/
	black --check pysrc/ tests/
	isort --check pysrc/ tests/
	cargo fmt -- --check
	python -m slotscheck pysrc/

.PHONY: clean
clean:
	python setup.py clean --all
	rm -rf build/ dist/ pysrc/**/*.so pysrc/**/__pycache__ *.egg-info **/*.egg-info \
		docs/_build/ htmlcov/ .mypy_cache/ .pytest_cache/ target/

.PHONY: develop
develop:
	python setup.py build_ext --inplace
