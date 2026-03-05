#!/bin/bash
# Run the Bedtime Stories API server
cd "$(dirname "$0")"
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
