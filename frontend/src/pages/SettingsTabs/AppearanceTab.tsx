import React from 'react';
import { Box, Typography, FormControl, InputLabel, Select, MenuItem } from '@mui/material';
import { useThemeContext } from '../../contexts/ThemeContext';

export default function AppearanceTab() {
  const { theme, setTheme } = useThemeContext();

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Tema da Aplicação
      </Typography>
      <FormControl sx={{ minWidth: 200 }}>
        <InputLabel id="theme-label">Tema</InputLabel>
        <Select
          labelId="theme-label"
          value={theme}
          label="Tema"
          onChange={e => setTheme(e.target.value)}
        >
          <MenuItem value="light">Claro</MenuItem>
          <MenuItem value="dark">Escuro</MenuItem>
          <MenuItem value="system">Sistema</MenuItem>
          <MenuItem value="solarized-dark">Solarized Dark</MenuItem>
          <MenuItem value="red-dark">Red Dark</MenuItem>
          <MenuItem value="green-forest">Green Forest</MenuItem>
          <MenuItem value="ocean-blue">Ocean Blue</MenuItem>
          <MenuItem value="purple-night">Purple Night</MenuItem>
        </Select>
      </FormControl>
    </Box>
  );
}