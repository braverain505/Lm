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

const API_URL = (process.env.API_URL || 'https://schoolos-api-5066.onrender.com/api').replace(/\/$/, '');

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
  // Construct the backend URL
  const url = new URL(`${API_URL}${pathname}`);
  url.search = searchParams.toString();

  console.log(`[API Proxy] ${method} ${pathname} → ${url.toString()}`);

  // Build request options
  const fetchOptions: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
      // Forward auth headers from the client
      ...(requestHeaders?.get('authorization') && {
        'Authorization': requestHeaders.get('authorization') || '',
      }),
      ...(requestHeaders?.get('cookie') && {
        'Cookie': requestHeaders.get('cookie') || '',
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

    // Return the response with appropriate status
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error(`[API Proxy] Error forwarding ${method} ${pathname}:`, error);
    return NextResponse.json(
      { error: 'Failed to reach backend API' },
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
