# Makefile for the credentio C2PA validator spike (Phase 1 subset).

.PHONY: help install build-credentio testdata demo clean

help:
	@echo "Usage:"
	@echo "  make install          Install Python deps (c2pa-python, demo-compare only)"
	@echo "  make build-credentio  Clone + Bazel-build credentio //tools:c2pa_validate into bin/"
	@echo "  make testdata         Fetch the real signed C2PA fixture into testdata/"
	@echo "  make demo             Run runner->adapter and diff against c2pa-python"
	@echo "  make clean            Remove caches and downloaded binary"

install:
	export UV_DEFAULT_INDEX=https://pypi.org/simple && uv sync

build-credentio:
	./scripts/build_credentio.sh

testdata:
	./scripts/fetch_testdata.sh

demo:
	python scripts/demo.py

clean:
	rm -rf __pycache__ credentio_validator/__pycache__ scripts/__pycache__
	rm -f bin/c2pa_validate
	@echo "Cleaned."
