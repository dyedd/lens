import { Globe2 } from "lucide-react";
import { useState } from "react";
import { getSiteFaviconCandidates } from "./channelDisplay";

/** Renders a site favicon with fallback candidates and a generic icon. */
export function SiteFavicon({ url, name }: { url: string; name: string }) {
  const [candidateIndex, setCandidateIndex] = useState(0);
  const candidates = getSiteFaviconCandidates(url);
  const currentSrc = candidates[candidateIndex];

  return (
    <span className="flex size-11 items-center justify-center rounded-xl border bg-background/80">
      {currentSrc ? (
        <img
          src={currentSrc}
          alt=""
          className="size-5 rounded-sm object-contain"
          loading="lazy"
          onError={() => {
            setCandidateIndex((current) =>
              current < candidates.length - 1 ? current + 1 : current,
            );
          }}
        />
      ) : (
        <Globe2 aria-hidden="true" className="text-muted-foreground" />
      )}
      <span className="sr-only">{name}</span>
    </span>
  );
}
