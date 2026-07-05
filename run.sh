#!/bin/bash
kill $(lsof -ti:8000) 2>/dev/null
set -a
source .env
set +a
uvicorn src.main:app --reload
