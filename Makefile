SHELL := /bin/bash
VENV := backend/.venv
# PY is relative to backend/ (the repo path may contain spaces, so never expand absolute paths unquoted)
PY := .venv/bin/python
PORT ?= 8000

.PHONY: help install dev backend frontend train seed test reset check-whatsapp build-demo demo

help:
	@echo "make install          install backend + frontend dependencies"
	@echo "make dev              backend (:$(PORT)) + frontend (:5173) with hot reload"
	@echo "make train            generate synthetic data and train the model"
	@echo "make seed             reset DB and seed demo personas"
	@echo "make test             run backend tests (pass ARGS='-k name')"
	@echo "make check-whatsapp   validate WhatsApp credentials and send a test message"
	@echo "make build-demo       install, train (if needed) and build the frontend"
	@echo "make demo             single-origin server (backend serves built frontend)"

$(VENV)/bin/python:
	python3.11 -m venv $(VENV)
	$(VENV)/bin/pip install -q -r backend/requirements.txt

install: $(VENV)/bin/python
	cd frontend && npm install

backend:
	cd backend && $(PY) -m uvicorn app.main:app --reload --port $(PORT)

frontend:
	cd frontend && npm run dev

dev:
	@trap 'kill 0' EXIT; \
	(cd backend && $(PY) -m uvicorn app.main:app --reload --port $(PORT)) & \
	(cd frontend && npm run dev) & \
	wait

train:
	cd backend && $(PY) -m ml.train --force-data

seed reset:
	cd backend && $(PY) -m app.seed

test:
	cd backend && $(PY) -m pytest -q $(ARGS)

check-whatsapp:
	cd backend && $(PY) ../scripts/check_whatsapp.py $(ARGS)

build-demo: install
	@test -f backend/ml/artifacts/model.joblib || $(MAKE) train
	cd frontend && npm run build

demo:
	cd backend && $(PY) -m uvicorn app.main:app --port $(PORT)
