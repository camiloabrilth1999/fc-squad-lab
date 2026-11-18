import { classifyUrl, isFutUrl, sanitizeUrl } from "./parse";

export interface HookTarget {
  fetch?: typeof fetch;
  XMLHttpRequest?: typeof XMLHttpRequest;
  postMessage: (msg: unknown, origin: string) => void;
}

/**
 * Observa fetch y XHR sin alterar petición ni respuesta. Todo observador va en
 * try/catch y no relanza; jamás emite peticiones propias.
 */
export function installHook(
  target: HookTarget,
  isRawMode: () => boolean,
  onResponse: (url: string) => void = () => {},
): void {
  const seen = (url: string): void => {
    try {
      onResponse(url);
    } catch {
      /* ignorar */
    }
  };
  const wanted = (url: string): boolean => {
    try {
      return classifyUrl(url) !== null || (isRawMode() && isFutUrl(url));
    } catch {
      return false;
    }
  };
  const emit = (url: string, body: unknown): void => {
    try {
      // Solo {url sin query, body}: nunca cabeceras, cookies ni tokens.
      target.postMessage({ source: "fcsl", url: sanitizeUrl(url), body }, "*");
    } catch {
      /* ignorar */
    }
  };

  const origFetch = target.fetch;
  if (typeof origFetch === "function") {
    target.fetch = function (this: unknown, ...args: Parameters<typeof fetch>) {
      const result = origFetch.apply(this, args);
      try {
        const input = args[0];
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input?.url;
        result
          .then((res) => {
            try {
              if (!url || res.status !== 200) return;
              seen(url);
              if (!wanted(url)) return;
              res
                .clone()
                .json()
                .then((body) => emit(url, body))
                .catch(() => {});
            } catch {
              /* ignorar */
            }
          })
          .catch(() => {});
      } catch {
        /* ignorar */
      }
      return result;
    } as typeof fetch;
  }

  const XHR = target.XMLHttpRequest;
  if (XHR?.prototype) {
    const origOpen = XHR.prototype.open;
    XHR.prototype.open = function (this: XMLHttpRequest, ...args: unknown[]) {
      try {
        (this as unknown as { __fcslUrl?: string }).__fcslUrl = String(args[1]);
      } catch {
        /* ignorar */
      }
      return (origOpen as (...a: unknown[]) => void).apply(this, args);
    } as typeof origOpen;
    const origSend = XHR.prototype.send;
    XHR.prototype.send = function (this: XMLHttpRequest, ...args: unknown[]) {
      try {
        this.addEventListener("load", () => {
          try {
            const url = (this as unknown as { __fcslUrl?: string }).__fcslUrl;
            if (!url || this.status !== 200) return;
            seen(url);
            if (!wanted(url)) return;
            const text = this.responseType === "" || this.responseType === "text" ? this.responseText : null;
            const data = text ?? (this.responseType === "json" ? this.response : null);
            const body = typeof data === "string" ? JSON.parse(data) : data;
            if (body !== null && body !== undefined) emit(url, body);
          } catch {
            /* ignorar */
          }
        });
      } catch {
        /* ignorar */
      }
      return (origSend as (...a: unknown[]) => void).apply(this, args);
    } as typeof origSend;
  }
}
