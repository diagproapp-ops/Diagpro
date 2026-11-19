// components/ImagemPreview.tsx
import React from "react";

export default function ImagemPreview({ src, alt, ...rest }: { src: string; alt?: string; [key: string]: any }) {
  return (
    <img
      src={src}
      alt={alt || "Preview"}
      style={{
        maxWidth: "100%",
        maxHeight: 320,
        height: "auto",
        width: "auto",
        objectFit: "contain",
        borderRadius: 4,
        border: "1px solid rgba(148, 163, 184, 0.25)",
        display: "block",
        margin: "0 auto"
      }}
      {...rest}
    />
  );
}