import React from 'react';
import { Box, Typography, FormControl, InputLabel, Select, MenuItem, Stack, Chip } from '@mui/material';
import { useThemeContext } from '../../contexts/ThemeContext';

const THEME_OPTIONS = [
  { value: 'operan-dark', label: 'Operan Pro Dark (Padrão)', color: '#0EA5E9' },
  { value: 'ocean-blue', label: 'Ocean Blue', color: '#38BDF8' },
  { value: 'purple-night', label: 'Purple Night', color: '#A855F7' },
  { value: 'green-forest', label: 'Emerald Forest', color: '#10B981' },
  { value: 'solarized-dark', label: 'Solarized Dark', color: '#268bd2' },
  { value: 'red-dark', label: 'Crimson Dark', color: '#EF4444' },
  { value: 'light', label: 'Claro (Clean Light)', color: '#0284C7' },
  { value: 'system', label: 'Automático do Sistema', color: '#64748B' },
];

export default function AppearanceTab() {
  const { theme, setTheme } = useThemeContext();

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} gutterBottom>
        Identidade Visual e Tema da Interface
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Escolha a paleta visual da plataforma. A alteração é aplicada instantaneamente e salva no seu navegador.
      </Typography>

      <FormControl sx={{ minWidth: 300, mb: 3 }}>
        <InputLabel id="theme-label">Tema Ativo</InputLabel>
        <Select
          labelId="theme-label"
          value={theme}
          label="Tema Ativo"
          onChange={(e) => setTheme(e.target.value)}
        >
          {THEME_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: opt.color }} />
                <span>{opt.label}</span>
              </Stack>
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
        {THEME_OPTIONS.map((opt) => (
          <Chip
            key={opt.value}
            label={opt.label}
            onClick={() => setTheme(opt.value)}
            variant={theme === opt.value ? 'filled' : 'outlined'}
            color={theme === opt.value ? 'primary' : 'default'}
            sx={{ borderRadius: 2, fontWeight: 600 }}
          />
        ))}
      </Stack>
    </Box>
  );
}
