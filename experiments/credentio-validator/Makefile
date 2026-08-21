# Makefile for the credentio C2PA validator spike (Phase 1 subset).

.PHONY: help install install-service build-credentio testdata demo test serve docker clean

help:
	@echo "Usage:"
	@echo "  make install          Install core Python deps (c2pa-python, demo-compare only)"
	@echo "  make install-service  Install service extras (fastapi, uvicorn, pydantic, requests)"
	@echo "  make build-credentio  Clone + Bazel-build credentio //tools:c2pa_validate into bin/"
	@echo "  make testdata         Fetch the real signed C2PA fixture into testdata/"
	@echo "  make demo             Run runner->adapter and diff against c2pa-python"
	@echo "  make test             Run the pytest suite"
	@echo "  make serve            Run the FastAPI service locally (uvicorn, :8000)"
	@echo "  make docker           Build the multi-stage service image"
	@echo "  make clean            Remove caches and built binary"

install:
	export UV_DEFAULT_INDEX=https://pypi.org/simple && uv sync

install-service:
	export UV_DEFAULT_INDEX=https://pypi.org/simple && uv sync --extra service

test:
	python -m pytest -q

serve:
	uvicorn credentio_validator.service:app --host 0.0.0.0 --port 8000

docker:
	docker build -t credentio-validator:spike .

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
