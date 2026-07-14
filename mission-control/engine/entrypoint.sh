#!/bin/bash
set -e

# OpenMontage engine entrypoint for Mission Control
# Injects credentials, model routing, and provider overrides
# from environment, then delegates to the normal make target

if [ -n "$FORCED_PROVIDERS" ]; then
  echo "$FORCED_PROVIDERS" > /app/config/forced_providers.json
fi

if [ -n "$MODEL_ROUTING" ]; then
  echo "$MODEL_ROUTING" > /app/config/model_routing.json
fi

exec "$@"
