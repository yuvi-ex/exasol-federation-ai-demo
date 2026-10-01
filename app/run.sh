#!/usr/bin/env bash
# Start the demo page: http://localhost:${PORT:-8510}
cd "$(dirname "$0")"
exec python -m streamlit run app.py --server.port "${PORT:-8510}" --server.headless true --browser.gatherUsageStats false
