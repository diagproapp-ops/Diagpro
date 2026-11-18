import { Button, Typography, Box } from "@mui/material";
import PhotoCamera from "@mui/icons-material/PhotoCamera";
import { useEffect, useState } from "react";

export default function FileInputMui({
  label, file, onChange
}: { label: string, file: File | null, onChange: (file: File | null) => void }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (file) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setPreviewUrl(null);
    }
  }, [file]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <Button
        variant="contained"
        component="label"
        color="secondary"
        startIcon={<PhotoCamera />}
        sx={{ mt: 1, mb: 1, textTransform: "none" }}
      >
        {label}
        <input
          type="file"
          accept="image/*"
          hidden
          onChange={e => onChange(e.target.files?.[0] || null)}
        />
      </Button>
      {file && (
        <Typography variant="body2" sx={{ mt: 0.5, color: "#666", textAlign: "center" }}>
          {file.name}
        </Typography>
      )}
      {previewUrl && (
        <Box sx={{ mt: 1, mb: 2, display: "flex", justifyContent: "center" }}>
          <img src={previewUrl} alt="preview" style={{ maxWidth: 200, maxHeight: 120, borderRadius: 8 }} />
        </Box>
      )}
    </Box>
  );
}