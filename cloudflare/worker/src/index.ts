export interface Env {
  NEURO_SPACE_BASE: string;
  AUDITOR_SPACE_BASE: string;
  NEURO_SPACE_TOKEN?: string;
  AUDITOR_SPACE_TOKEN?: string;
}

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

function buildTargetUrl(base: string, suffix: string, search: string): string {
  const target = new URL(base);
  const normalizedBase = target.pathname.endsWith("/")
    ? target.pathname.slice(0, -1)
    : target.pathname;
  target.pathname = `${normalizedBase}/${suffix}`.replace(/\/+/g, "/");
  target.search = search;
  return target.toString();
}

async function proxySpace(
  request: Request,
  targetBase: string,
  token: string | undefined,
  suffix: string,
  search: string,
): Promise<Response> {
  const init: RequestInit = {
    method: request.method,
    headers: new Headers(),
    redirect: "manual",
  };

  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      init.headers!.set(key, value);
    }
  });

  if (token) {
    init.headers!.set("Authorization", `Bearer ${token}`);
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
  }

  const response = await fetch(buildTargetUrl(targetBase, suffix, search), init);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: new Headers(response.headers),
  });
}

function routeSuffix(url: URL, prefix: string): string {
  const raw = url.pathname.slice(prefix.length);
  return raw.replace(/^\//, "");
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname.startsWith("/neuro/")) {
      const suffix = routeSuffix(url, "/neuro");
      return proxySpace(request, env.NEURO_SPACE_BASE, env.NEURO_SPACE_TOKEN, suffix, url.search);
    }

    if (url.pathname.startsWith("/auditor/")) {
      const suffix = routeSuffix(url, "/auditor");
      return proxySpace(request, env.AUDITOR_SPACE_BASE, env.AUDITOR_SPACE_TOKEN, suffix, url.search);
    }

    if (url.pathname === "/" || url.pathname === "") {
      return Response.json(
        {
          ok: true,
          message: "Proxy Worker online",
          routes: {
            neuro: "/neuro/*",
            auditor: "/auditor/*",
          },
        },
        { headers: { "Cache-Control": "no-store" } },
      );
    }

    return new Response("Not Found", { status: 404 });
  },
};
