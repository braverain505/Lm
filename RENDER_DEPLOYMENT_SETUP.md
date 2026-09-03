# Render Deployment Setup Guide

This guide explains how to configure your Render.com deployment for the Lumo SaaS application with the new Base64 logo storage and API proxy routing.

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
STORAGE_BASE_DIR=/tmp/schoolos/storage

# Other existing env vars...
```

**Important:** The `STORAGE_BASE_DIR=/tmp/schoolos/storage` path is **ephemeral** on Render free tier — files are deleted on redeploy. This is acceptable because:
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
   npm run build --workspace=@schoolos/web
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

- **API Proxy**: Adds ~50-100ms latency per request (server-side round-trip). Acceptable for most use cases.
- **Base64 Logos**: Slightly larger database size (~3-5x larger than file paths), but 1 GB PostgreSQL free tier can handle thousands of logos.

## Future Improvements

- **S3 Storage**: Migrate to AWS S3 for unlimited file storage (free tier: 5 GB/month)
- **Persistent Disk**: Upgrade to Render's paid tier to add a persistent disk ($7/month minimum)
- **CDN**: Add CloudFront for logo caching to reduce proxy latency

---

For questions or issues, check the Render logs or contact support at https://support.render.com
