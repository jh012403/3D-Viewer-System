const ROUTES = new Set(["/", "/image"]);

export function normalizePath(pathname = window.location.pathname) {
  if (!pathname) {
    return "/";
  }

  let normalized = pathname;
  if (normalized.length > 1 && normalized.endsWith("/")) {
    normalized = normalized.slice(0, -1);
  }

  return ROUTES.has(normalized) ? normalized : "/";
}

export function currentPath() {
  return normalizePath(window.location.pathname);
}

export function readQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

export function navigate(path, options = {}) {
  const { replace = false, query = {} } = options;
  const url = new URL(window.location.href);
  url.pathname = normalizePath(path);
  url.search = "";

  Object.entries(query).forEach(([key, value]) => {
    if (value) {
      url.searchParams.set(key, value);
    }
  });

  window.history[replace ? "replaceState" : "pushState"]({}, "", `${url.pathname}${url.search}`);
  window.dispatchEvent(new Event("app:navigate"));
}

export function initRouter(render) {
  const handler = () => render(currentPath());

  window.addEventListener("popstate", handler);
  window.addEventListener("app:navigate", handler);
  handler();

  return () => {
    window.removeEventListener("popstate", handler);
    window.removeEventListener("app:navigate", handler);
  };
}
