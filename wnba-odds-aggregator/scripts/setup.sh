#!/bin/bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config/.env.example config/.env
python scripts/init_db.py 