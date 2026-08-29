import { getStoredToken } from "@/lib/auth";

type ApiErrorPayload = {
  error?: {
    message?: string;
    details?: Array<{ loc?: Array<string | number>; msg?: string }>;
  };
};

/** Represents an unsuccessful API response with its HTTP status. */
export class ApiError extends Error {
  status: number;
  override cause?: unknown;

  constructor(message: string, status: number, cause?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.cause = cause;
  }
}

/** Returns an API error message or the supplied fallback. */
export function getApiErrorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

function parseJsonResponse<T>(
  text: string,
  status: number,
  context: string,
): T {
  try {
    return JSON.parse(text) as T;
  } catch (parseError) {
    throw new ApiError(`${context}: ${String(parseError)}`, status, parseError);
  }
}

export async function apiFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (typeof init?.body === "string" && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const token = getStoredToken();
  if (token) headers.set("authorization", `Bearer ${token}`);

  const response = await fetch(`/api${path}`, { ...init, headers });
  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    const text = await response.text();
    let errorMessage = "";
    if (contentType.includes("application/json") && text) {
      const payload = parseJsonResponse<ApiErrorPayload>(
        text,
        response.status,
        "Invalid JSON error response from API",
      );
      if (payload.error?.message) {
        errorMessage = payload.error.message;
        const detail = payload.error.details?.[0];
        if (detail) {
          const field = detail.loc
            ? detail.loc.filter((item) => item !== "body").join(".")
            : "";
          if (field && detail.msg) {
            errorMessage += `: ${field}: ${detail.msg}`;
          }
        }
      }
    }
    throw new ApiError(
      errorMessage || text || `Request failed with status ${response.status}`,
      response.status,
    );
  }
  return response;
}

/** Sends an authenticated API request and parses its JSON response. */
export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await apiFetch(path, init);
  if (response.status === 204) return undefined as T;
  return parseJsonResponse<T>(
    await response.text(),
    response.status,
    "Invalid JSON response from API",
  );
}
