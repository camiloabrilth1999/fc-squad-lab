const CDN = "https://game-assets.fut.gg/cdn-cgi/image";

/** URL de una imagen del CDN de FUT.GG a partir de la ruta guardada; `null` si no hay ruta. */
export function imageUrl(path: string | null | undefined, width = 200): string | null {
  if (!path) return null;
  return `${CDN}/quality=85,format=auto,width=${width}/${path.replace(/^\/+/, "")}`;
}
