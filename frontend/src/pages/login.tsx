import React, { useState, useRef, useEffect } from 'react';
import ReCAPTCHA from 'react-google-recaptcha';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Box, Button, TextField, Typography, Paper, Stack, Link, CssBaseline, CircularProgress, Alert } from '@mui/material';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [recaptchaToken, setRecaptchaToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const recaptchaRef = useRef<ReCAPTCHA>(null);
  const navigate = useNavigate();

  const isMounted = useRef(true);
  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recaptchaToken) {
      if (isMounted.current) setError("Por favor, complete a verificação 'Não sou um robô'.");
      return;
    }
    if (isMounted.current) {
      setError(null);
      setLoading(true);
    }
    try {
      // login deve guardar também role e client_id
      await login(username, password, recaptchaToken);
      if (isMounted.current) navigate('/dashboard');
    } catch (err: any) {
      if (isMounted.current) {
        setError(err?.response?.data?.detail || 'Falha no login.');
        try { recaptchaRef.current?.reset(); } catch(_) {}
        setRecaptchaToken(null);
      }
    }
    if (isMounted.current) setLoading(false);
  };

  return (
    <>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: { xs: 'column', sm: 'row' }}}>
        <Box
          sx={{
            flex: 1,
            display: { xs: 'none', sm: 'block' },
            backgroundImage: 'url(https://source.unsplash.com/random?technology,abstract)',
            backgroundSize: 'cover'
          }}
        />
        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: { xs: 2, sm: 4 } }}>
          <Paper elevation={3} sx={{ width: { xs: '100%', sm: 360 }, p: 4, textAlign: 'center' }}>
            <Stack spacing={2}>
              <Typography variant="h4" sx={{ fontWeight: 700 }}>DiagProOFF</Typography>
              <Box component="form" onSubmit={handleSubmit}>
                <Stack spacing={2}>
                  <TextField
                    label="Nome de usuário"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    fullWidth
                  />
                  <TextField
                    label="Senha"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    fullWidth
                  />
                  <Box sx={{ display: 'flex', justifyContent: 'center', my: 1 }}>
                    <ReCAPTCHA
                      ref={recaptchaRef}
                      sitekey="6LcTjaorAAAAAOOMZ15DfNDVsLFdqZA-oW1klht4"
                      onChange={(token) => setRecaptchaToken(token)}
                      onExpired={() => setRecaptchaToken(null)}
                    />
                  </Box>
                  {error && <Alert severity="error">{error}</Alert>}
                  <Button
                    type="submit"
                    variant="contained"
                    disabled={loading}
                    sx={{ py: 1.5 }}
                    fullWidth
                  >
                    {loading ? <CircularProgress size={24} /> : 'Entrar'}
                  </Button>
                </Stack>
              </Box>
              <Link href="#" variant="body2">Esqueceu a senha?</Link>
            </Stack>
          </Paper>
        </Box>
      </Box>
    </>
  );
}