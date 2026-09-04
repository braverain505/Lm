/**
 * API Proxy Route Handler
 *
 * Proxies all backend API requests server-side to avoid CORS/DNS issues.
 * Frontend calls /api/proxy/... which forwards to the Render backend.
 *
 * Benefits:
 * - Hides the direct backend URL from the browser
 * - Avoids CORS issues (same-origin requests)
 * - Solves DNS resolution errors from ephemeral Render containers
 * - Private environment variables protected from browser exposure
 */

import { NextRequest, NextResponse } from 'next/server';

// Read and clean the API_URL environment variable
const API_URL = (process.env.API_URL || 'https://schoolos-api-5066.onrender.com/api')
  .trim()
  .replace(/\/$/, '');



/**
 * Forward request to backend API
 */
async function forwardRequest(
  method: string,
  pathname: string,
  searchParams: URLSearchParams,
  body?: any,
  request?: NextRequest,
) {
  // Construct the backend URL safely
  let url: URL;
  try {
    // Remove leading slash from pathname if API_URL already has path
    const cleanPath = pathname.startsWith('/') ? pathname.slice(1) : pathname;
    const fullUrl = `${API_URL}/${cleanPath}`;
    url = new URL(fullUrl);
    url.search = searchParams.toString();
  } catch (error) {
    console.error('[API Proxy] Invalid URL construction:', error);
    console.error('[API Proxy] API_URL:', API_URL);
    console.error('[API Proxy] pathname:', pathname);
    return NextResponse.json(
      { error: 'Invalid backend URL configuration', details: String(error) },
      { status: 500 }
    );
  }



  // Forward cookies from incoming request to backend
  const cookieHeader = request?.headers.get('cookie');
  const headers = new Headers();

  // Detect if this is a FormData (multipart) upload
  const contentType = request?.headers.get('content-type') || '';
  const isMultipart = contentType.includes('multipart/form-data');

  // For multipart uploads, do NOT set Content-Type — the browser must
  // set it automatically with the correct boundary string.
  if (!isMultipart) {
    headers.set('Content-Type', 'application/json');
  }

  // Forward authorization header if present
  const authHeader = request?.headers.get('authorization');
  if (authHeader) {
    headers.set('Authorization', authHeader);
  }

  // Forward X-School-Id header for tenant resolution
  const schoolId = request?.headers.get('x-school-id');
  if (schoolId) {
    headers.set('X-School-Id', schoolId);
  }

  // Forward cookies to backend
  if (cookieHeader) {
    headers.set('Cookie', cookieHeader);
  }

  try {
    let response: Response;

    if (isMultipart && request && ['POST', 'PUT', 'PATCH'].includes(method)) {
      // Re-encode the incoming FormData and let the runtime generate a fresh
      // multipart boundary. Passing the raw Request through (or copying the
      // original Content-Type header) makes the backend receive either no
      // boundary or a stale one that matches nothing, so it sees zero parts
      // and rejects the upload with "file: Field required".
      const forwardHeaders = new Headers();
      const fwdAuth = request.headers.get('authorization');
      if (fwdAuth) forwardHeaders.set('Authorization', fwdAuth);
      const fwdSchool = request.headers.get('x-school-id');
      if (fwdSchool) forwardHeaders.set('X-School-Id', fwdSchool);
      if (cookieHeader) forwardHeaders.set('Cookie', cookieHeader);

      const form = await request.formData();
      response = await fetch(url.toString(), {
        method,
        headers: forwardHeaders,
        body: form,
      });
    } else {
      // Build request options for non-multipart requests
      const fetchOptions: RequestInit = {
        method,
        headers,
      };

      if (['POST', 'PUT', 'PATCH'].includes(method) && body) {
        fetchOptions.body = JSON.stringify(body);
      }

      response = await fetch(url.toString(), fetchOptions);
    }

    // Extract response body
    const data = await response.json().catch(() => response.text());



    // Create the response
    const nextResponse = NextResponse.json(data, { status: response.status });

    // Forward ALL Set-Cookie headers from backend to client, rewriting their
    // Path so they match the proxy mount. The backend sets the refresh token at
    // Path=/api/auth, but the browser talks to /api/proxy/*, so without a rewrite
    // the refresh cookie is never sent back and the session 401s once the access
    // token expires. Map /api/ -> /api/proxy/ (a plain Path=/ stays Path=/).
    const setCookies = response.headers.getSetCookie();
    if (setCookies && setCookies.length > 0) {

      setCookies.forEach(cookie => {
        const rewritten = cookie.replace(/;\s*Path=\/api\//i, '; Path=/api/proxy/');
        nextResponse.headers.append('Set-Cookie', rewritten);
      });
    }

    return nextResponse;
  } catch (error) {
    console.error(`[API Proxy] Error forwarding ${method} ${pathname}:`, error);
    console.error(`[API Proxy] Target URL was: ${url.toString()}`);
    console.error(`[API Proxy] API_URL env var: ${API_URL}`);
    return NextResponse.json(
      { error: 'Failed to reach backend API', details: String(error) },
      { status: 502 }
    );
  }
}

/**
 * GET /api/proxy/...
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathname = `/${path.join('/')}`;
  const searchParams = request.nextUrl.searchParams;

  return forwardRequest('GET', pathname, searchParams, undefined, request);
}

/**
 * POST /api/proxy/...
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathname = `/${path.join('/')}`;
  const searchParams = request.nextUrl.searchParams;

  let body;
  // Never JSON-parse a multipart body: .json() drains the request stream even
  // when the parse fails, so multipart uploads would be forwarded empty and the
  // backend would reject them with "file: Field required" (ERR_VALIDATION 422).
  if (!(request.headers.get('content-type') || '').includes('multipart/form-data')) {
    try {
      body = await request.json();
    } catch {
      body = undefined;
    }
  }

  return forwardRequest('POST', pathname, searchParams, body, request);
}

/**
 * PUT /api/proxy/...
 */
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathname = `/${path.join('/')}`;
  const searchParams = request.nextUrl.searchParams;

  let body;
  // Never JSON-parse a multipart body: .json() drains the request stream even
  // when the parse fails, so multipart uploads would be forwarded empty and the
  // backend would reject them with "file: Field required" (ERR_VALIDATION 422).
  if (!(request.headers.get('content-type') || '').includes('multipart/form-data')) {
    try {
      body = await request.json();
    } catch {
      body = undefined;
    }
  }

  return forwardRequest('PUT', pathname, searchParams, body, request);
}

/**
 * PATCH /api/proxy/...
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathname = `/${path.join('/')}`;
  const searchParams = request.nextUrl.searchParams;

  let body;
  // Never JSON-parse a multipart body: .json() drains the request stream even
  // when the parse fails, so multipart uploads would be forwarded empty and the
  // backend would reject them with "file: Field required" (ERR_VALIDATION 422).
  if (!(request.headers.get('content-type') || '').includes('multipart/form-data')) {
    try {
      body = await request.json();
    } catch {
      body = undefined;
    }
  }

  return forwardRequest('PATCH', pathname, searchParams, body, request);
}

/**
 * DELETE /api/proxy/...
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathname = `/${path.join('/')}`;
  const searchParams = request.nextUrl.searchParams;

  return forwardRequest('DELETE', pathname, searchParams, undefined, request);
}
