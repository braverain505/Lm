# Render Deployment Setup Guide

This guide explains how to configure your Render.com deployment for the Clearis SaaS application with the new Base64 logo storage and API proxy routing.

## Overview

Your Render deployment consists of:
- **Next.js Frontend** (apps/web) — deployed as a Node.js service on Render
- **Python API Backend** (apps/api) — deployed as another Node.js or Python service on Render
- **PostgreSQL Database** — a managed Postgres database on Render (free tier: 1 GB)

### Recent Changes

1. **Base64 Logo Storage** — School logos are now stored as Base64 strings directly in PostgreSQL instead of using the local filesystem (which is ephemeral on Render free tier)
2. **API Proxy Route** — Frontend now routes API requests through `/api/proxy/[...path]` instead of calling the backend directly, solving CORS and DNS issues

## Environment Variables Setup

### Frontend Service Environment Variables

On your Render frontend service, add these environment variables:

```env
# Optional: Override the API proxy base URL (default is /api/proxy)
NEXT_PUBLIC_API_URL=/api/proxy

# Backend API URL (used server-side by the proxy route)
API_URL=https://schoolos-api-5066.onrender.com/api

# Other existing env vars...
```

**Where to set:**
1. Go to Render Dashboard → Your Frontend Service
2. Click "Environment" tab
3. Add the variables above
4. Click "Save Changes"
5. Trigger a redeploy

### Backend Service Environment Variables

On your Render API service, ensure these are set:

```env
# Database connection (should already be set)
DATABASE_URL=postgresql://...

# Storage configuration for Render free tier
STORAGE_DRIVER=local
STORAGE_BASE_DIR=/tmp/clearis/storage

# Other existing env vars...
```

**Important:** The `STORAGE_BASE_DIR=/tmp/clearis/storage` path is **ephemeral** on Render free tier — files are deleted on redeploy. This is acceptable because:
- **School logos** are now stored as Base64 in PostgreSQL (persistent)
- **Student photos** can remain in local storage (will be wiped on redeploy, but you can migrate them to Base64 later if needed)

**Where to set:**
1. Go to Render Dashboard → Your Backend Service
2. Click "Environment" tab
3. Add/update the variables above
4. Click "Save Changes"
5. Trigger a redeploy

## Testing the Changes

### 1. Test the API Proxy

After deploying, verify that API requests go through the proxy:

1. Open your frontend at https://www.clearis.site
2. Open browser DevTools → Network tab
3. Trigger any API call (e.g., login)
4. You should see requests to:
   - `https://www.clearis.site/api/proxy/auth/login` (not the direct backend URL)
5. The request should succeed and return data from the backend

### 2. Test Logo Upload

1. Go to Settings → School Settings
2. Upload a new school logo
3. The upload should succeed
4. Refresh the page
5. The logo should still be visible (persisted in PostgreSQL)

### 3. Check Logs

- **Frontend logs**: Render Dashboard → Frontend Service → "Logs" tab
- **Backend logs**: Render Dashboard → Backend Service → "Logs" tab

Look for any errors related to API proxy or logo uploads.

## Troubleshooting

### Logo Upload Returns 404

**Problem:** Upload succeeds but retrieval fails with 404

**Solutions:**
1. **Clear browser cache** — if logo was stored as a filesystem path before, old URLs may be cached
2. **Check database** — verify the logo_url is stored in the schools table:
   ```sql
   SELECT id, name, logo_url FROM schools WHERE id = 'your-school-id';
   ```
   Should show a data URL like: `data:image/png;base64,iVBORw0KG...`
3. **Check API logs** — look for errors in the backend logs during upload

### API Calls Return CORS Errors

**Problem:** API calls fail with CORS errors

**Solutions:**
1. **Verify proxy is installed** — ensure the file exists at `apps/web/src/app/api/proxy/[...path]/route.ts`
2. **Check Next.js build** — rebuild the frontend:
   ```bash
   npm run build --workspace=@clearis/web
   ```
3. **Verify environment variable** — ensure `API_URL` is set on the frontend service in Render

### API Calls Return 502 Bad Gateway

**Problem:** API proxy returns 502

**Solutions:**
1. **Check backend is running** — verify the backend service is online in Render Dashboard
2. **Verify API_URL is correct** — check that `API_URL` environment variable points to the correct backend URL
3. **Check logs** — look at proxy route logs for error messages

## Rollback (If Needed)

If you need to revert to direct backend URLs (not recommended):

**Frontend:** Update the API client base URL back to direct backend:
```typescript
// In packages/shared/src/client.ts
const BASE = (
  process.env.NEXT_PUBLIC_API_URL ??
  "https://schoolos-api-5066.onrender.com/api"  // <-- direct URL
).replace(/\/$/, "");
```

Then rebuild and redeploy the frontend.

## Performance Notes

Measured 2026-11-06 against the production API and database.

### 1. Fix first: the API and the database are in different regions

| Component | Where it actually runs |
|---|---|
| API (`schoolos-api-5066.onrender.com`) | Render, **GCP us-west1 (Oregon)** — resolves to `gcp-us-west1-1.origin.onrender.com` |
| Database | Neon, **AWS us-east-2 (Ohio)** — `ep-…c-6.us-east-2.aws.neon.tech` |

Oregon and Ohio are ~3,200 km apart, so **every SQL statement is a cross-country round trip of roughly 60–80 ms**. The dashboard endpoint issues **34 sequential queries**, so it spends ~2.2 s waiting on the network before either service has done any real work.

This is not Render's CPU and not Neon's query planning. Evidence: a `count(*)` over a 74-row table measured ~250 ms — no database takes 250 ms to count 74 rows; that number is the round trip. Meanwhile the API's `/` endpoint, which touches no database at all, answers as fast as the origin allows.

**Fix (no extra cost):** make the two colocated — either recreate the Render API service in **Ohio (`us-east-2`)**, or move the Neon project to **us-west-2**. Same 34 queries then cost ~35 ms instead of ~2.2 s.

> Render region cannot be changed in place. Create a new service in Ohio with the same environment variables and root directory, verify it, then switch the frontend's `API_URL` / `NEXT_PUBLIC_API_URL` to the new host. Neon has no in-place region move either: create a project in us-west-2 and restore a dump into it.

### 2. Second: cold starts

The first request after a period of inactivity measured up to **59 s** end-to-end; the trivial `/` endpoint took 1.8–12 s. Cheap tiers scale to zero — Render stops the instance and Neon suspends compute — so the first person in each morning pays the wake-up for everyone. That is the "sometimes login takes a while" feeling.

**Fix (free):** point an uptime monitor at `GET /api/health` **every 5 minutes** (UptimeRobot, Better Stack, cron-job.org all have free plans). That endpoint runs `SELECT 1`, which keeps both the Render instance and the Neon compute awake. Use the same URL as Render's health check path.

### 3. Application-side changes already made

- **Per-request school context: 4 queries → 1.** `get_school_context` used to fetch membership, school, role and permission codes as four sequential statements on *every* authenticated request. It is now one joined query with the permission codes aggregated inline.
- **Password hashing cost 12 → 10.** A login check measured 349 ms at cost 12 and 88 ms at cost 10 on the server CPU. New hashes use cost 10 (`BCRYPT_ROUNDS` overrides it); existing hashes are re-hashed automatically the first time each user signs in.
- **Neon pooled endpoint.** Point `DATABASE_URL` at the `-pooler` host (`ep-…-pooler.c-6.us-east-2.aws.neon.tech`) so connection setup is multiplexed. Keep `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` conservative.
- **API Proxy**: routes through the Next.js service, adding one server-side hop per call. If the API and web services are in different Render regions, that is a second cross-country trip — check both services' regions, or point `NEXT_PUBLIC_API_URL` directly at the API origin (keeping CORS configured) to remove the hop.
- **Base64 Logos**: Slightly larger database size (~3-5x larger than file paths), but the database can handle thousands of logos.

## Future Improvements

- **S3 Storage**: Migrate to AWS S3 for unlimited file storage (free tier: 5 GB/month)
- **Persistent Disk**: Upgrade to Render's paid tier to add a persistent disk ($7/month minimum)
- **CDN**: Add CloudFront for logo caching to reduce proxy latency

---

For questions or issues, check the Render logs or contact support at https://support.render.com
