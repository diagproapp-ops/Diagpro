import { useState } from "react";

export default function FullscreenButton({ children }: { children: React.ReactNode }) {
  const [fullscreen, setFullscreen] = useState(false);
  return (
    <>
      <button onClick={() => setFullscreen(true)}>Tela cheia</button>
      {fullscreen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "#fff",
            zIndex: 9999,
            padding: 16,
          }}
        >
          <button
            onClick={() => setFullscreen(false)}
            style={{ position: "absolute", top: 10, right: 10 }}
          >
            Fechar
          </button>
          {children}
        </div>
      )}
    </>
  );
}