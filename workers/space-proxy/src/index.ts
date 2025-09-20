interface Env {
  HF_TOKEN?: string;
  NEURO_SPACE?: string;
  AUDITOR_SPACE?: string;
}

type SpaceRoute = {
  prefix: string;
  spaceId: string;
};

const DEFAULT_ROUTES: SpaceRoute[] = [
  { prefix: "/neuro", spaceId: "darkfrostx/neuro-mechanism-backend" },
  { prefix: "/auditor", spaceId: "darkfrostx/ssra-auditor" },
];

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const routes = buildRoutes(env);
    const url = new URL(request.url);
    const match = matchRoute(url.pathname, routes);

    if (!match) {
      return jsonResponse({ error: "Unknown route" }, 404);
    }

    const targetUrl = buildTargetUrl(match, url);
    const init = await buildFetchInit(request, env);

    try {
      const upstream = await fetch(targetUrl, init);
      const headers = new Headers(upstream.headers);
      applyCors(headers);
      return new Response(upstream.body, {
        status: upstream.status,
        headers,
      });
    } catch (err) {
      return jsonResponse({ error: "Failed to reach Hugging Face Space", detail: String(err) }, 502);
    }
  },
};

function buildRoutes(env: Env): SpaceRoute[] {
  const routes = [...DEFAULT_ROUTES];

  if (env.NEURO_SPACE) {
    routes[0] = { prefix: "/neuro", spaceId: env.NEURO_SPACE };
  }
  if (env.AUDITOR_SPACE) {
    routes[1] = { prefix: "/auditor", spaceId: env.AUDITOR_SPACE };
  }

  return routes;
}

function matchRoute(pathname: string, routes: SpaceRoute[]): SpaceRoute | undefined {
  for (const route of routes) {
    if (pathname === route.prefix || pathname.startsWith(route.prefix + "/")) {
      return route;
    }
  }
  return undefined;
}

function buildTargetUrl(route: SpaceRoute, incoming: URL): string {
  const slug = route.spaceId.replace(/\//g, "-");
  const suffix = incoming.pathname.slice(route.prefix.length) || "/";
  const normalized = suffix.startsWith("/") ? suffix : `/${suffix}`;
  const target = new URL(`https://${slug}.hf.space${normalized}`);
  target.search = incoming.search;
  return target.toString();
}

async function buildFetchInit(request: Request, env: Env): Promise<RequestInit> {
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.set("accept", headers.get("accept") ?? "application/json");
  if (env.HF_TOKEN) {
    headers.set("Authorization", `Bearer ${env.HF_TOKEN}`);
  }
  applyCors(headers);

  let body: ArrayBuffer | undefined;
  if (!isBodylessMethod(request.method)) {
    body = await request.arrayBuffer();
  }

  return {
    method: request.method,
    headers,
    body,
    redirect: "follow",
  };
}

function isBodylessMethod(method: string): boolean {
  return method === "GET" || method === "HEAD";
}

function applyCors(headers: Headers): void {
  for (const [key, value] of Object.entries(CORS_HEADERS)) {
    headers.set(key, value);
  }
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      "content-type": "application/json",
      ...CORS_HEADERS,
    },
  });
}
