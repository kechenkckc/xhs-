export async function api(url, options = {}) {
  const { allowBusinessError = false, ...fetchOptions } = options;
  const response = await fetch(url, {
    ...fetchOptions,
    headers: { 'Content-Type': 'application/json', ...(fetchOptions.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || (!allowBusinessError && payload.ok === false)) {
    const detail = payload.detail || payload;
    const message = detail?.message || detail?.error || payload.message || payload.error || response.statusText || '请求失败';
    const error = new Error(message);
    error.detail = detail;
    throw error;
  }
  return payload;
}

export function formatApiErrorMessage(payload, fallback = '请求失败') {
  if (!payload) return fallback;
  if (typeof payload === 'string') return payload;
  if (payload instanceof Error) return payload.message || fallback;

  const detail = payload.detail && typeof payload.detail === 'object' ? payload.detail : payload;
  const directMessage = detail.message || detail.error || payload.message || payload.error;
  if (typeof directMessage === 'string') return directMessage;
  if (directMessage && typeof directMessage === 'object') {
    return formatApiErrorMessage(directMessage, fallback);
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return fallback;
  }
}
