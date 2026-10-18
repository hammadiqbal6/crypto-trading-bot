#!/usr/bin/env bash
set -euo pipefail
cd /app

case "${1:-dashboard}" in
  dashboard)
    exec crypto-bot dashboard
    ;;
  validate)
    exec crypto-bot validate
    ;;
  freqtrade-trade)
    crypto-bot export-freqtrade-config --out /app/config/freqtrade/config.json
    exec freqtrade trade -c /app/config/freqtrade/config.json --strategy VolatilityMomentumStrategy
    ;;
  *)
    exec "$@"
    ;;
esac
