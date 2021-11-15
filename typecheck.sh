#!/bin/bash
python3 -m mypy retrotracker.py --ignore-missing-imports
python3 -m mypy modify.py --ignore-missing-imports
python3 -m mypy query.py --ignore-missing-imports
