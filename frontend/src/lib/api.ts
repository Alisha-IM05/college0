export interface JsonResponse {
  ok: boolean;
  redirect?: string;
  error?: string;
  message?: string;
  data?: Record<string, unknown>;
}

interface PostOptions {
  bearerToken?: string | null;
}

/**
 * POST form data to a Flask route that supports our JSON contract.
 * Backend returns { ok, redirect?, error?, message? } when Accept is JSON.
 */
export async function postForm(
  url: string,
  body: Record<string, string> | FormData,
  opts: PostOptions = {},
): Promise<JsonResponse> {
  const fd = body instanceof FormData ? body : toFormData(body);
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Requested-With': 'fetch',
  };
  if (opts.bearerToken) {
    headers.Authorization = `Bearer ${opts.bearerToken}`;
  }
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers,
      body: fd,
      credentials: 'same-origin',
    });
    const ct = resp.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      const data = (await resp.json()) as JsonResponse;
      return data;
    }
    if (resp.redirected) {
      return { ok: resp.ok, redirect: resp.url };
    }
    return { ok: resp.ok, error: resp.ok ? undefined : `Request failed (${resp.status}).` };
  } catch (err) {
    return { ok: false, error: (err as Error).message || 'Network error.' };
  }
}

function toFormData(obj: Record<string, string>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(obj)) fd.append(k, v);
  return fd;
}

export function navigate(url: string): void {
  window.location.assign(url);
}
