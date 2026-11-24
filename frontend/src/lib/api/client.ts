import { getStoredToken, signOut } from "@/lib/auth";

/** Represents an unsuccessful API response with its HTTP status. */
export class ApiError extends Error {
  status: number;
  errorType?: string;
  constructor(
    message: string,
    status: number,
    cause?: unknown,
    errorType?: string,
  ) {
    super(message, cause === undefined ? undefined : { cause });
    this.name = "ApiError";
    this.status = status;
    this.errorType = errorType;
  }
}

/** Returns an API error message or the supplied fallback. */
export function getApiErrorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
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

/**
 * An admin HTTP 401 signs out the current token unless it came from login
 * or an aborted request. Unsuccessful responses throw an ApiError.
 */
export async function apiFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (typeof init?.body === "string" && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const isAdminLogin =
    path === "/admin/session" && init?.method?.toUpperCase() === "POST";
  const requiresAdminSession = path.startsWith("/admin/") && !isAdminLogin;
  const token = requiresAdminSession ? getStoredToken() : "";
  if (token) headers.set("authorization", `Bearer ${token}`);

  const response = await fetch(`/api${path}`, { ...init, headers });
  if (
    response.status === 401 &&
    requiresAdminSession &&
    !init?.signal?.aborted &&
    token &&
    token === getStoredToken()
  ) {
    signOut();
  }
  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    let text: string;
    try {
      text = await response.text();
    } catch (readError) {
      if (init?.signal?.aborted) throw readError;
      throw new ApiError(
        `Request failed with status ${response.status}`,
        response.status,
        readError,
      );
    }
    let errorMessage = "";
    let errorType: string | undefined;
    if (contentType.includes("application/json") && text) {
      let payload: unknown;
      try {
        payload = JSON.parse(text);
      } catch (parseError) {
        throw new ApiError(text, response.status, parseError);
      }
      const error =
        isRecord(payload) && isRecord(payload.error) ? payload.error : null;
      if (typeof error?.type === "string") errorType = error.type;
      if (typeof error?.message === "string" && error.message) {
        errorMessage = error.message;
        const detail = Array.isArray(error.details)
          ? error.details[0]
          : undefined;
        if (isRecord(detail)) {
          const field = Array.isArray(detail.loc)
            ? detail.loc
                .filter(
                  (item): item is string | number =>
                    typeof item === "string" || typeof item === "number",
                )
                .filter((item) => item !== "body")
                .join(".")
            : "";
          if (field && typeof detail.msg === "string" && detail.msg) {
            errorMessage += `: ${field}: ${detail.msg}`;
          }
        }
      }
    }
    throw new ApiError(
      errorMessage || text || `Request failed with status ${response.status}`,
      response.status,
      undefined,
      errorType,
    );
  }
  return response;
}

/** Parses JSON from apiFetch, including its admin 401 session handling. */
export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await apiFetch(path, init);
  let text: string;
  try {
    text = await response.text();
  } catch (readError) {
    if (init?.signal?.aborted) throw readError;
    throw new ApiError(
      "Failed to read response from API",
      response.status,
      readError,
    );
  }
  return parseJsonResponse<T>(
    text,
    response.status,
    "Invalid JSON response from API",
  );
}
