export interface Env {
  HUGGING_FACE_API_BASE?: string;
  HF_API_TOKEN?: string;
  NEURO_REPO_ID: string;
  AUDITOR_REPO_ID: string;
  NEURO_REPO_REVISION?: string;
  AUDITOR_REPO_REVISION?: string;
  NEURO_REPO_TOKEN?: string;
  AUDITOR_REPO_TOKEN?: string;
}

const DEFAULT_BASE = "https://huggingface.co";
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

type Route = "neuro" | "auditor";

interface RouteConfig {
  repoId: string;
  defaultRevision?: string;
  token?: string;
}

function sanitizeHeaders(headers: Headers): Headers {
  const result = new Headers();
  headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      result.set(key, value);
    }
  });
  return result;
}

function encodeRepoId(repoId: string): string {
  return repoId
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

function encodePath(path: string): string {
  return path
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

function buildRepoResourceUrl(
  base: string,
  repoId: string,
  revision: string,
  suffix: string,
  searchParams: URLSearchParams,
): string {
  if (!suffix) {
    const url = new URL(`${base}/api/models/${encodeRepoId(repoId)}`);
    if (revision) {
      url.searchParams.set("revision", revision);
    }
    searchParams.forEach((value, key) => url.searchParams.append(key, value));
    return url.toString();
  }

  const encodedPath = encodePath(suffix);
  const target = new URL(
    `${base}/${encodeRepoId(repoId)}/resolve/${encodeURIComponent(revision)}/${encodedPath}`,
  );
  const leftover = searchParams.toString();
  if (leftover) {
    target.search = leftover;
  }
  return target.toString();
}

function routeSuffix(url: URL, prefix: string): string {
  const raw = url.pathname.slice(prefix.length);
  return raw.replace(/^\//, "");
}

function pickRouteConfig(env: Env, route: Route): RouteConfig {
  if (route === "neuro") {
    return {
      repoId: env.NEURO_REPO_ID,
      defaultRevision: env.NEURO_REPO_REVISION,
      token: env.NEURO_REPO_TOKEN ?? env.HF_API_TOKEN,
    };
  }
  return {
    repoId: env.AUDITOR_REPO_ID,
    defaultRevision: env.AUDITOR_REPO_REVISION,
    token: env.AUDITOR_REPO_TOKEN ?? env.HF_API_TOKEN,
  };
}

async function proxyRepository(
  request: Request,
  env: Env,
  route: Route,
  suffix: string,
): Promise<Response> {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method Not Allowed", {
      status: 405,
      headers: { Allow: "GET, HEAD" },
    });
  }

  const url = new URL(request.url);
  const params = new URLSearchParams(url.search);
  const config = pickRouteConfig(env, route);
  const revision = params.get("revision") ?? config.defaultRevision ?? "main";
  params.delete("revision");

  const base = env.HUGGING_FACE_API_BASE ?? DEFAULT_BASE;
  const targetUrl = buildRepoResourceUrl(base, config.repoId, revision, suffix, params);

  const forwardHeaders = sanitizeHeaders(request.headers);
  if (config.token) {
    forwardHeaders.set("Authorization", `Bearer ${config.token}`);
  }

  const init: RequestInit = {
    method: request.method,
    headers: forwardHeaders,
    redirect: "manual",
  };

  const response = await fetch(targetUrl, init);
  const responseHeaders = sanitizeHeaders(response.headers);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname.startsWith("/neuro")) {
      const suffix = routeSuffix(url, "/neuro");
      return proxyRepository(request, env, "neuro", suffix);
    }

    if (url.pathname.startsWith("/auditor")) {
      const suffix = routeSuffix(url, "/auditor");
      return proxyRepository(request, env, "auditor", suffix);
    }

    if (url.pathname === "/" || url.pathname === "") {
      return Response.json(
        {
          ok: true,
          message: "Hugging Face repository proxy online",
          routes: {
            neuro: "/neuro/<path>?revision=<branch>",
            auditor: "/auditor/<path>?revision=<branch>",
          },
        },
        { headers: { "Cache-Control": "no-store" } },
      );
    }

    return new Response("Not Found", { status: 404 });
  },
};
