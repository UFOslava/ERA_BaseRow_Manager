#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ERA BaseRow Manager - WSL dev runner (manual start)
#
#   ./scripts/dev.sh            start backend (MCP on) + frontend in tmux
#   ./scripts/dev.sh backend    start only the backend
#   ./scripts/dev.sh frontend   start only the frontend
#   ./scripts/dev.sh attach     attach to the tmux session
#   ./scripts/dev.sh stop       stop the tmux session
#   ./scripts/dev.sh status     show status + port health
#
# Backend : http://localhost:5000   (MCP SSE on 0.0.0.0:8001)
# Frontend: http://localhost:3000
# ---------------------------------------------------------------------------
set -euo pipefail

SESSION="era"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
VENV="$HOME/era-venv"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" >/dev/null 2>&1 || true

BACKEND_CMD="cd '$ROOT/backend' && exec '$VENV/bin/python' run.py --mcp-host 0.0.0.0"
FRONTEND_CMD="cd '$ROOT/frontend' && exec npm run dev"

need_tmux() {
  command -v tmux >/dev/null 2>&1 || { echo "!! tmux missing (sudo apt install tmux)"; exit 1; }
}

preflight_backend() {
  [ -x "$VENV/bin/python" ] || { echo "!! missing venv: $VENV"; exit 1; }
  [ -f "$ROOT/backend/run.py" ] || { echo "!! missing backend/run.py"; exit 1; }
  if systemctl is-active --quiet era-bom.service 2>/dev/null; then
    echo "!! era-bom.service is running and holds :5000"
    echo "   disable it first:  sudo systemctl disable --now era-bom.service"
    exit 1
  fi
}

preflight_frontend() {
  command -v npm >/dev/null 2>&1 || { echo "!! npm not found (is nvm loaded?)"; exit 1; }
  [ -d "$ROOT/frontend/node_modules" ] || { echo "!! frontend deps missing - run: (cd $ROOT/frontend && npm install)"; exit 1; }
}

# start a named window in the session, creating the session if needed
start_window() {
  local name="$1" cmd="$2"
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    if tmux list-windows -t "$SESSION" -F '#{window_name}' | grep -qx "$name"; then
      echo "   window '$name' already exists - skipping"
      return 0
    fi
    tmux new-window -t "$SESSION" -n "$name" "bash -lc \"$cmd\""
  else
    tmux new-session -d -s "$SESSION" -n "$name" "bash -lc \"$cmd\""
  fi
}

case "${1:-all}" in
  all)
    need_tmux; preflight_backend; preflight_frontend
    tmux has-session -t "$SESSION" 2>/dev/null && { echo "session '$SESSION' already running (use: $0 stop)"; exit 1; }
    start_window backend  "$BACKEND_CMD"
    start_window frontend "$FRONTEND_CMD"
    echo "started  backend :5000  MCP :8001  frontend :3000"
    echo "attach   tmux attach -t $SESSION   (or: $0 attach)"
    ;;
  backend)
    need_tmux; preflight_backend
    start_window backend "$BACKEND_CMD"
    echo "started  backend :5000  MCP :8001"
    ;;
  frontend)
    need_tmux; preflight_frontend
    start_window frontend "$FRONTEND_CMD"
    echo "started  frontend :3000"
    ;;
  attach)
    exec tmux attach -t "$SESSION"
    ;;
  stop)
    tmux kill-session -t "$SESSION" 2>/dev/null && echo "stopped" || echo "not running"
    ;;
  status)
    if tmux has-session -t "$SESSION" 2>/dev/null; then
      tmux list-windows -t "$SESSION"
    else
      echo "tmux session '$SESSION' not running"
    fi
    curl -s -o /dev/null -w "backend  :5000 -> %{http_code}\n" --max-time 3 http://127.0.0.1:5000/api/auth/status || true
    curl -s -o /dev/null -w "mcp      :8001 -> %{http_code}\n" --max-time 3 http://127.0.0.1:8001/sse || true
    curl -s -o /dev/null -w "frontend :3000 -> %{http_code}\n" --max-time 3 http://127.0.0.1:3000/ || true
    ;;
  *)
    sed -n '2,15p' "$0"
    exit 1
    ;;
esac
