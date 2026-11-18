import type { Editor } from "@tiptap/react";

export default function FileUploadButton({ editor }: { editor: Editor }) {
  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      const url = URL.createObjectURL(file);
      editor.chain().focus().insertContent(`<a href="${url}" target="_blank">${file.name}</a>`).run();
    }
  }
  return <input type="file" onChange={handleFile} />;
}