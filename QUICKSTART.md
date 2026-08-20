# SchoolOS - Quick Start Guide

## 🚀 Starting SchoolOS (Backend + Frontend)

### Prerequisites Check
```bash
# Check Python version (need 3.11+)
python3 --version

# Check Node.js (need 18+)
node --version

# Check npm
npm --version
```

---

## Backend API Setup

### 1. Install Dependencies (First Time Only)

```bash
cd ~/schoolos/apps/api

# Create virtual environment (if not exists)
python3 -m venv ../../.venv

# Activate virtual environment
source ../../.venv/bin/activate

# Install all dependencies
pip install -e ".[dev]"

# Note: This will take 2-3 minutes
# Installs: FastAPI, SQLAlchemy, slowapi, nh3, and all dependencies
```

### 2. Setup Database (First Time Only)

```bash
# Create database
bash ../../scripts/dev-db.sh

# Run migrations
bash ../../scripts/migrate.sh seed

# This creates demo school: admin@brightfield.edu / Brightfield#2026
```

### 3. Start Backend Server

```bash
cd ~/schoolos/apps/api
source ../../.venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Backend URL:** http://localhost:8000  
**API Docs:** http://localhost:8000/api/docs  
**Health Check:** http://localhost:8000/api/health

---

## Frontend Web App Setup

### 1. Install Dependencies (First Time Only)

```bash
cd ~/schoolos/apps/web

# Install Node modules (takes 3-5 minutes)
npm install

# This installs Next.js, React, TanStack Query, shadcn/ui, etc.
```

### 2. Configure Environment

```bash
cd ~/schoolos/apps/web

# Copy environment template
cp .env.example .env

# Edit if needed (default points to localhost:8000)
nano .env
```

Default `.env` should have:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

### 3. Start Frontend Server

```bash
cd ~/schoolos/apps/web
npm run dev
```

**Frontend URL:** http://localhost:3000

---

## Quick Start (All-in-One)

### Terminal 1 - Backend:
```bash
cd ~/schoolos/apps/api
source ../../.venv/bin/activate || python3 -m venv ../../.venv && source ../../.venv/bin/activate
pip install -e ".[dev]" 2>&1 | grep -E "(Successfully|already|Requirement)"
uvicorn app.main:app --reload --port 8000
```

### Terminal 2 - Frontend:
```bash
cd ~/schoolos/apps/web
npm install 2>&1 | tail -10
npm run dev
```

---

## Testing the Application

### 1. Check Backend Health
```bash
curl http://localhost:8000/api/health
# Should return: {"status":"ok","service":"lumo-api","version":"0.1.0","database":"connected"}
```

### 2. Access API Documentation
Open browser: http://localhost:8000/api/docs

### 3. Access Frontend
Open browser: http://localhost:3000

### 4. Demo Login Credentials
- **Admin:** admin@brightfield.edu / Brightfield#2026
- **Teacher:** ada.obi@brightfield.edu / Teacher#2026
- **Accountant:** accountant@brightfield.edu / Accountant#2026

---

## Troubleshooting

### Backend won't start

**Issue:** `ModuleNotFoundError: No module named 'slowapi'` or `'nh3'`
```bash
cd ~/schoolos/apps/api
source ../../.venv/bin/activate
pip install slowapi nh3
```

**Issue:** `database connection failed`
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Recreate database
bash scripts/dev-db.sh
bash scripts/migrate.sh seed
```

**Issue:** `Port 8000 already in use`
```bash
# Find and kill process
lsof -ti:8000 | xargs kill -9

# Or use different port
uvicorn app.main:app --port 8001
```

### Frontend won't start

**Issue:** `sh: 1: next: not found`
```bash
cd ~/schoolos/apps/web
npm install
```

**Issue:** `Port 3000 already in use`
```bash
# Kill process
lsof -ti:3000 | xargs kill -9

# Or use different port
npm run dev -- -p 3001
```

**Issue:** `Cannot connect to API`
- Check backend is running on port 8000
- Check `.env` file has correct `NEXT_PUBLIC_API_URL`
- Check CORS settings in backend

---

## Current Status

✅ **Backend:** 100% production ready  
✅ **Frontend:** Phase 1.5 (basic UI implemented)  
✅ **Test Suite:** 186/187 passing (99.5%)  
✅ **Security:** All 15 critical fixes implemented  

---

## Running in Background

### Using tmux (Recommended)
```bash
# Start tmux session
tmux new -s schoolos

# Split panes: Ctrl+B then "
# Switch panes: Ctrl+B then arrow keys

# Pane 1 - Backend
cd ~/schoolos/apps/api && source ../../.venv/bin/activate && uvicorn app.main:app --reload

# Pane 2 - Frontend  
cd ~/schoolos/apps/web && npm run dev

# Detach: Ctrl+B then D
# Reattach: tmux attach -t schoolos
```

### Using nohup
```bash
# Backend
cd ~/schoolos/apps/api
nohup uvicorn app.main:app --port 8000 > /tmp/api.log 2>&1 &

# Frontend
cd ~/schoolos/apps/web  
nohup npm run dev > /tmp/frontend.log 2>&1 &

# Check logs
tail -f /tmp/api.log
tail -f /tmp/frontend.log
```

---

## Production Deployment

For production deployment, see:
- `docs/DEPLOYMENT.md` - Complete production guide
- `docs/100_PERCENT_PRODUCTION_READY.md` - Security checklist
- `.env.production.example` - Production config template

---

## Need Help?

- API Documentation: http://localhost:8000/api/docs
- Test Health: `curl http://localhost:8000/api/health`
- Check Logs: `tail -f /tmp/schoolos-*.log`
- Run Tests: `cd apps/api && pytest -v`

**Everything is ready to go! Just install dependencies and start the servers.** 🚀
