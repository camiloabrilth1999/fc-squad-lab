/* eslint-disable @next/next/no-img-element -- imágenes externas del CDN, sin optimizador de Next */
import { imageUrl } from "../lib/images";

/** Imagen de la carta completa; si no hay ruta, un recuadro con la media y la posición. */
export default function CardImage({
  path,
  rating,
  position,
  alt,
  width = 200,
  className = "",
}: {
  path?: string | null;
  rating?: number | null;
  position?: string | null;
  alt: string;
  width?: number;
  className?: string;
}) {
  const src = imageUrl(path, width * 1.5);
  if (src) {
    return (
      <img
        src={src}
        alt={alt}
        loading="lazy"
        decoding="async"
        className={`aspect-[5/7] w-full scale-[1.12] object-contain ${className}`}
      />
    );
  }
  return (
    <div
      role="img"
      aria-label={alt}
      className={`grid aspect-[5/7] w-full place-items-center rounded-lg bg-surface-2 text-center ${className}`}
    >
      <span className="font-mono text-2xl font-semibold tabular-nums">
        {rating === undefined ? "" : (rating ?? "–")}
        <span className="block text-xs font-normal text-muted">{position ?? ""}</span>
      </span>
    </div>
  );
}

/** Escudo o bandera pequeños (nación, club, liga). */
export function Badge({ path, alt, size = 18 }: { path?: string | null; alt: string; size?: number }) {
  const src = imageUrl(path, size * 2);
  if (!src) return null;
  return (
    <img
      src={src}
      alt={alt}
      title={alt}
      loading="lazy"
      width={size}
      height={size}
      className="inline-block object-contain"
      style={{ width: size, height: size }}
    />
  );
}
