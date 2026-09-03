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

import { headers } from 'next/headers';

const API_URL = process.env.API_URL || 'https://schoolos-api-5066.onrender.com';

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

    // Return the response with appropriate status
    return Response.json(data, { status: response.status });
  } catch (error) {
    console.error(`[API Proxy] Error forwarding ${method} ${pathname}:`, error);
    return Response.json(
      { error: 'Failed to reach backend API' },
      { status: 502 }
    );
  }
}

/**
 * GET /api/proxy/...
 */
export async function GET(
  request: Request,
  { params }: { params: { path: string[] } }
) {
  const pathname = `/${params.path.join('/')}`;
  const searchParams = new URL(request.url).searchParams;
  const requestHeaders = await headers();

  return forwardRequest('GET', pathname, searchParams, undefined, requestHeaders);
}

/**
 * POST /api/proxy/...
 */
export async function POST(
  request: Request,
  { params }: { params: { path: string[] } }
) {
  const pathname = `/${params.path.join('/')}`;
  const searchParams = new URL(request.url).searchParams;
  const requestHeaders = await headers();

  let body;
  try {
    body = await request.json();
  } catch {
    body = undefined;
  }

  return forwardRequest('POST', pathname, searchParams, body, requestHeaders);
}

/**
 * PUT /api/proxy/...
 */
export async function PUT(
  request: Request,
  { params }: { params: { path: string[] } }
) {
  const pathname = `/${params.path.join('/')}`;
  const searchParams = new URL(request.url).searchParams;
  const requestHeaders = await headers();

  let body;
  try {
    body = await request.json();
  } catch {
    body = undefined;
  }

  return forwardRequest('PUT', pathname, searchParams, body, requestHeaders);
}

/**
 * PATCH /api/proxy/...
 */
export async function PATCH(
  request: Request,
  { params }: { params: { path: string[] } }
) {
  const pathname = `/${params.path.join('/')}`;
  const searchParams = new URL(request.url).searchParams;
  const requestHeaders = await headers();

  let body;
  try {
    body = await request.json();
  } catch {
    body = undefined;
  }

  return forwardRequest('PATCH', pathname, searchParams, body, requestHeaders);
}

/**
 * DELETE /api/proxy/...
 */
export async function DELETE(
  request: Request,
  { params }: { params: { path: string[] } }
) {
  const pathname = `/${params.path.join('/')}`;
  const searchParams = new URL(request.url).searchParams;
  const requestHeaders = await headers();

  return forwardRequest('DELETE', pathname, searchParams, undefined, requestHeaders);
}
