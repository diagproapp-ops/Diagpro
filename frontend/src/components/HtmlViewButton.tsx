import { useState } from "react";
import type { Editor } from "@tiptap/react";

export default function HtmlViewButton({ editor }: { editor: Editor }) {
  const [show, setShow] = useState(false);
  return (
    <>
      <button onClick={() => setShow(s => !s)}>Ver HTML</button>
      {show && <pre>{editor.getHTML()}</pre>}
    </>
  );
}