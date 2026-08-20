#!/usr/bin/env bash
# Start the Next.js dev server in the background (used by dev tooling).
cd ~/schoolos/apps/web
nohup npm run dev > /tmp/schoolos-web.log 2>&1 &
echo "started pid $!"