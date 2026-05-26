export async function api(url, options = {}) {
  const {
    allowBusinessError = false,
    timeoutMs = 0,
    timeoutMessage = '请求超时，请稍后重试',
    ...fetchOptions
  } = options;
  const timeoutEnabled = Number(timeoutMs) > 0;
  const controller = timeoutEnabled ? new AbortController() : null;
  const callerSignal = fetchOptions.signal;
  let timedOut = false;
  let timeoutId = null;
  let abortHandler = null;

  if (controller) {
    if (callerSignal?.aborted) {
      controller.abort(callerSignal.reason);
    } else if (callerSignal) {
      abortHandler = () => controller.abort(callerSignal.reason);
      callerSignal.addEventListener('abort', abortHandler, { once: true });
    }
    timeoutId = globalThis.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, Number(timeoutMs));
  }

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller?.signal || callerSignal,
      headers: { 'Content-Type': 'application/json', ...(fetchOptions.headers || {}) },
    });
    const text = await response.text();
    let payload = {};
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = { message: text.slice(0, 500) };
      }
    }
    if (!response.ok || (!allowBusinessError && payload.ok === false)) {
      const detail = payload.detail || payload;
      const message = detail?.message || detail?.error || payload.message || payload.error || response.statusText || '请求失败';
      const error = new Error(message);
      error.detail = detail;
      throw error;
    }
    return payload;
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error(timedOut ? timeoutMessage : '请求已取消');
    }
    throw error;
  } finally {
    if (timeoutId) globalThis.clearTimeout(timeoutId);
    if (callerSignal && abortHandler) {
      callerSignal.removeEventListener('abort', abortHandler);
    }
  }
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
