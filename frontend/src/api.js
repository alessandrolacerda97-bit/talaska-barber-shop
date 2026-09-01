const rawApiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export const API_URL = rawApiUrl.replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

export async function api(path, options = {}) {
  const {
    method = 'GET',
    body,
    token,
    signal,
    headers: extraHeaders = {},
  } = options;
  const headers = { ...extraHeaders };
  let requestBody = body;

  if (body !== undefined && body !== null && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    requestBody = JSON.stringify(body);
  }
  if (token) headers.Authorization = 'Bearer ' + token;

  let response;
  try {
    response = await fetch(API_URL + path, {
      method,
      headers,
      body: requestBody,
      signal,
    });
  } catch {
    throw new ApiError('Não foi possível conectar ao sistema. Tente novamente em instantes.', 0);
  }

  const contentType = response.headers.get('content-type') || '';
  let payload = null;
  if (contentType.includes('application/json')) {
    payload = await response.json().catch(() => null);
  } else {
    payload = await response.text().catch(() => null);
  }

  if (!response.ok) {
    const message = payload && typeof payload === 'object'
      ? (payload.detail || payload.message || 'Não foi possível concluir esta ação.')
      : 'Não foi possível concluir esta ação.';
    throw new ApiError(message, response.status, payload);
  }
  return payload;
}

export function query(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  });
  const result = search.toString();
  return result ? '?' + result : '';
}
