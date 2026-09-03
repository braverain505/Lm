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
import { cookies } from 'next/headers';

// Read and clean the API_URL environment variable
const API_URL = (process.env.API_URL || 'https://schoolos-api-5066.onrender.com/api')
  .trim()
  .replace(/\/$/, '');

console.log('[API Proxy] Loaded. API_URL:', API_URL);

/**
 * Forward request to backend API
 */
async function forwardRequest(
  method: string,
  pathname: string,
  searchParams: URLSearchParams,
  body?: any,
  requestHeaders?: Headers,
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

  console.log(`[API Proxy] ${method} ${pathname} → ${url.toString()}`);

  // Get cookies from Next.js cookies store
  const cookieStore = await cookies();
  const allCookies = cookieStore.getAll();
  const cookieHeader = allCookies.map(c => `${c.name}=${c.value}`).join('; ');

  // Build request options
  const fetchOptions: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
      // Forward auth headers from the client
      ...(requestHeaders?.get('authorization') && {
        'Authorization': requestHeaders.get('authorization') || '',
      }),
      // Forward cookies to backend
      ...(cookieHeader && {
        'Cookie': cookieHeader,
      }),
    },
  };

  // Add body for POST, PUT, PATCH requests
  if (body && ['POST', 'PUT', 'PATCH'].includes(method)) {
    fetchOptions.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(url.toString(), fetchOptions);

    // Extract response body
    const data = await response.json().catch(() => response.text());

    console.log(`[API Proxy] Response status: ${response.status}`);

    // Create the response
    const nextResponse = NextResponse.json(data, { status: response.status });

    // Forward Set-Cookie headers from backend to client
    const setCookieHeaders = response.headers.get('set-cookie');
    if (setCookieHeaders) {
      console.log('[API Proxy] Forwarding Set-Cookie headers from backend');
      nextResponse.headers.set('Set-Cookie', setCookieHeaders);
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

  console.log('[API Proxy] GET handler called with path:', path);

  return forwardRequest('GET', pathname, searchParams, undefined, request.headers);
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

  console.log('[API Proxy] POST handler called with path:', path);

  let body;
  try {
    body = await request.json();
  } catch {
    body = undefined;
  }

  return forwardRequest('POST', pathname, searchParams, body, request.headers);
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

  console.log('[API Proxy] PUT handler called with path:', path);

  let body;
  try {
    body = await request.json();
  } catch {
    body = undefined;
  }

  return forwardRequest('PUT', pathname, searchParams, body, request.headers);
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

  console.log('[API Proxy] PATCH handler called with path:', path);

  let body;
  try {
    body = await request.json();
  } catch {
    body = undefined;
  }

  return forwardRequest('PATCH', pathname, searchParams, body, request.headers);
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

  console.log('[API Proxy] DELETE handler called with path:', path);

  return forwardRequest('DELETE', pathname, searchParams, undefined, request.headers);
}
