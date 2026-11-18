import React from "react";
import { Picker } from "emoji-mart";
import "emoji-mart/css/emoji-mart.css";

export default function EmojiPickerButton({ editor }: { editor: any }) {
  const [open, setOpen] = React.useState(false);

  return (
    <div style={{ display: "inline-block", position: "relative" }}>
      <button onClick={() => setOpen(!open)}>😀</button>
      {open && (
        <div style={{ position: "absolute", zIndex: 10 }}>
          <Picker
            onEmojiSelect={(emoji: any) => {
              editor.chain().focus().insertContent(emoji.native).run();
              setOpen(false);
            }}
          />
        </div>
      )}
    </div>
  );
}