export interface Env {
  HF_API_BASE?: string;
  NEURO_REPO_ID: string;
  NEURO_REPO_TYPE?: string;
  NEURO_REPO_REVISION?: string;
  NEURO_REPO_TOKEN?: string;
  AUDITOR_REPO_ID: string;
  AUDITOR_REPO_TYPE?: string;
  AUDITOR_REPO_REVISION?: string;
  AUDITOR_REPO_TOKEN?: string;
}

type RepoScope = "models" | "datasets" | "spaces";
type RepoLabel = "model" | "dataset" | "space";

type Alias = "neuro" | "auditor";

interface RepoConfig {
  repoId: string;
  scope: RepoScope;
  label: RepoLabel;
  revision: string;
  token?: string;
}

const DEFAULT_BASE = "https://huggingface.co";
const DEFAULT_REVISION = "main";
const INFO_ROUTE = "__info__";
const FILES_ROUTE = "__files__";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "cf-connecting-ip",
  "cf-ew-via",
  "cf-ray",
  "cf-visitor",
]);

function normalizeRepoType(value?: string | null): { scope: RepoScope; label: RepoLabel } {
  const normalized = (value ?? "model").toLowerCase().replace(/s$/, "");
  switch (normalized) {
    case "model":
      return { scope: "models", label: "model" };
    case "dataset":
      return { scope: "datasets", label: "dataset" };
    case "space":
      return { scope: "spaces", label: "space" };
    default:
      throw new Error("repo type must be 'model', 'dataset', or 'space'");
  }
}

function readRepoConfig(env: Env, alias: Alias): RepoConfig {
  const upper = alias.toUpperCase();
  const bag = env as Record<string, string | undefined>;
  const repoId = bag[`${upper}_REPO_ID`];
  if (!repoId) {
    throw new Error(`Missing ${upper}_REPO_ID`);
  }
  const { scope, label } = normalizeRepoType(bag[`${upper}_REPO_TYPE`]);
  const revision = bag[`${upper}_REPO_REVISION`] ?? DEFAULT_REVISION;
  const token = bag[`${upper}_REPO_TOKEN`];
  return { repoId, scope, label, revision, token };
}

function encodeRepoId(repoId: string): string {
  return repoId
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

function encodeRepoPath(path: string): string {
  return path
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

function buildInfoUrl(baseUrl: string, config: RepoConfig): string {
  return `${baseUrl}/api/${config.scope}/${encodeRepoId(config.repoId)}`;
}

function buildTreeUrl(baseUrl: string, config: RepoConfig, params: URLSearchParams): string {
  const encodedRevision = encodeURIComponent(config.revision);
  const base = `${baseUrl}/api/${config.scope}/${encodeRepoId(config.repoId)}/tree/${encodedRevision}`;
  const query = params.toString();
  return query ? `${base}?${query}` : base;
}

function buildResolveUrl(baseUrl: string, config: RepoConfig, filePath: string): string {
  const encodedRevision = encodeURIComponent(config.revision);
  const encodedPath = encodeRepoPath(filePath);
  return `${baseUrl}/${encodeRepoId(config.repoId)}/resolve/${encodedRevision}/${encodedPath}`;
}

function routeSuffix(url: URL, prefix: string): string {
  const raw = url.pathname.slice(prefix.length);
  return raw.replace(/^\//, "");
}

function repoHeaders(token: string | undefined, accept = "application/json"): Headers {
  const headers = new Headers({ Accept: accept });
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

function forwardRequestHeaders(request: Request, token: string | undefined, accept?: string): Headers {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  if (accept && !headers.has("Accept")) {
    headers.set("Accept", accept);
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

function cloneHeaders(source: Headers): Headers {
  const headers = new Headers();
  source.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  return headers;
}

function wrapResponse(response: Response): Response {
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: cloneHeaders(response.headers),
  });
}

async function fetchRepoInfo(baseUrl: string, config: RepoConfig): Promise<Response> {
  const response = await fetch(buildInfoUrl(baseUrl, config), {
    headers: repoHeaders(config.token),
  });
  return wrapResponse(response);
}

async function fetchRepoFiles(baseUrl: string, config: RepoConfig, params: URLSearchParams): Promise<Response> {
  const search = new URLSearchParams(params);
  if (search.has("path")) {
    const raw = search.get("path") ?? "";
    const cleaned = raw.replace(/^\/+/, "");
    if (cleaned) {
      search.set("path", cleaned);
    } else {
      search.delete("path");
    }
  }
  if (!search.has("recursive")) {
    search.set("recursive", "1");
  }
  const response = await fetch(buildTreeUrl(baseUrl, config, search), {
    headers: repoHeaders(config.token),
  });
  return wrapResponse(response);
}

async function fetchRepoFile(request: Request, baseUrl: string, config: RepoConfig, filePath: string): Promise<Response> {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method Not Allowed", { status: 405 });
  }
  if (!filePath) {
    return Response.json({ ok: false, error: "File path missing" }, { status: 400 });
  }
  const targetUrl = buildResolveUrl(baseUrl, config, filePath);
  const init: RequestInit = {
    method: request.method,
    headers: forwardRequestHeaders(request, config.token, "*/*"),
    redirect: "manual",
  };
  const response = await fetch(targetUrl, init);
  return wrapResponse(response);
}

async function handleRepoRequest(
  request: Request,
  url: URL,
  baseUrl: string,
  prefix: string,
  config: RepoConfig,
): Promise<Response> {
  const suffix = routeSuffix(url, prefix);
  if (!suffix || suffix === INFO_ROUTE) {
    return fetchRepoInfo(baseUrl, config);
  }

  const [command, ...rest] = suffix.split("/");
  if (command === INFO_ROUTE) {
    return fetchRepoInfo(baseUrl, config);
  }
  if (command === FILES_ROUTE) {
    const params = new URLSearchParams(url.search);
    if (rest.length > 0 && !params.has("path")) {
      const inferred = rest.join("/");
      if (inferred) {
        params.set("path", inferred);
      }
    }
    return fetchRepoFiles(baseUrl, config, params);
  }

  return fetchRepoFile(request, baseUrl, config, suffix);
}

function summarizeAlias(env: Env, alias: Alias): Record<string, string> {
  try {
    const config = readRepoConfig(env, alias);
    return {
      repoId: config.repoId,
      repoType: config.label,
      revision: config.revision,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { error: message };
  }
}

function errorResponse(message: string, status = 500): Response {
  return Response.json({ ok: false, error: message }, { status });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const baseUrl = env.HF_API_BASE ?? DEFAULT_BASE;
    const aliases: Alias[] = ["neuro", "auditor"];

    for (const alias of aliases) {
      const prefix = `/${alias}`;
      if (url.pathname === prefix || url.pathname.startsWith(`${prefix}/`)) {
        try {
          const config = readRepoConfig(env, alias);
          return handleRepoRequest(request, url, baseUrl, prefix, config);
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          return errorResponse(message, 500);
        }
      }
    }

    if (url.pathname === "/" || url.pathname === "") {
      const repos: Record<string, Record<string, string>> = {};
      for (const alias of aliases) {
        repos[alias] = summarizeAlias(env, alias);
      }
      return Response.json(
        {
          ok: true,
          message: "Repository proxy online",
          routes: {
            info: INFO_ROUTE,
            files: FILES_ROUTE,
            raw: "<alias>/<file path>",
          },
          repos,
        },
        { headers: { "Cache-Control": "no-store" } },
      );
    }

    return new Response("Not Found", { status: 404 });
  },
};
