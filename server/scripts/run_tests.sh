#!/bin/bash
set -e
pytest tests/unit -m unit -v
pytest tests/integration -m integration -v
