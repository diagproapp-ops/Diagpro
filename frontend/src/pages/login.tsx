import React, { useState, useRef, useEffect } from 'react';
import ReCAPTCHA from 'react-google-recaptcha';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Typography,
  Stack,
  CssBaseline,
  CircularProgress,
  Alert,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import SupportIcon from '@mui/icons-material/Support';

/**
 * Canvas interativo: constelação de partículas + anel orbital ciano que SEGUE O MOUSE (estilo Operan)
 */
const MouseConstellationCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    // Posição alvo do mouse e posição suavizada (lerp) do núcleo ciano
    const mouse = {
      targetX: width * 0.42,
      targetY: height * 0.72,
      x: width * 0.42,
      y: height * 0.72,
    };

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
    };

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove);

    // Estrelas fixas/lentas no fundo espacial
    const stars = Array.from({ length: 130 }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      r: Math.random() * 1.3 + 0.3,
      alpha: Math.random() * 0.55 + 0.12,
      vy: (Math.random() - 0.5) * 0.12,
    }));

    // Nós da constelação que orbitam e seguem o cursor com inércia própria
    const nodes = Array.from({ length: 72 }, (_, i) => {
      const angle = (i / 72) * Math.PI * 2 + Math.random() * 0.6;
      const dist = 34 + Math.random() * 185;
      return {
        x: mouse.x + Math.cos(angle) * dist,
        y: mouse.y + Math.sin(angle) * dist,
        baseAngle: angle,
        dist,
        angularSpeed: (0.003 + Math.random() * 0.006) * (i % 2 === 0 ? 1 : -1),
        followFactor: 0.035 + Math.random() * 0.065,
        r: Math.random() * 2.3 + 0.9,
        pulse: Math.random() * Math.PI * 2,
      };
    });

    // Partículas densas do anel energético central
    const ringParticles = Array.from({ length: 64 }, (_, i) => ({
      angle: (i / 64) * Math.PI * 2,
      jitter: (Math.random() - 0.5) * 9,
      size: Math.random() * 2.5 + 1.1,
      speed: 0.01 + (Math.random() - 0.5) * 0.008,
    }));

    let tick = 0;

    const render = () => {
      tick += 0.016;
      // Suaviza o movimento do núcleo em direção ao mouse
      mouse.x += (mouse.targetX - mouse.x) * 0.11;
      mouse.y += (mouse.targetY - mouse.y) * 0.11;

      ctx.clearRect(0, 0, width, height);

      // Glow radial que acompanha o mouse
      const bgGlow = ctx.createRadialGradient(mouse.x, mouse.y, 8, mouse.x, mouse.y, 340);
      bgGlow.addColorStop(0, 'rgba(6, 182, 212, 0.25)');
      bgGlow.addColorStop(0.4, 'rgba(14, 165, 233, 0.08)');
      bgGlow.addColorStop(1, 'rgba(3, 8, 22, 0)');
      ctx.fillStyle = bgGlow;
      ctx.fillRect(0, 0, width, height);

      // Estrelas de fundo
      for (const s of stars) {
        s.y += s.vy;
        if (s.y < 0) s.y = height;
        if (s.y > height) s.y = 0;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(148, 163, 184, ${s.alpha})`;
        ctx.fill();
      }

      // Atualiza posição de cada nó com inércia em relação ao mouse
      for (const n of nodes) {
        n.baseAngle += n.angularSpeed;
        const wobble = Math.sin(tick * 1.6 + n.pulse) * 14;
        const targetNodeX = mouse.x + Math.cos(n.baseAngle) * (n.dist + wobble);
        const targetNodeY = mouse.y + Math.sin(n.baseAngle) * (n.dist + wobble);
        n.x += (targetNodeX - n.x) * n.followFactor;
        n.y += (targetNodeY - n.y) * n.followFactor;
      }

      // Conexões da constelação
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < 88) {
            const alpha = (1 - d / 88) * 0.34;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `rgba(34, 211, 238, ${alpha})`;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      }

      // Desenha nós da constelação
      for (const n of nodes) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(56, 189, 248, 0.85)';
        ctx.shadowColor = '#00E5FF';
        ctx.shadowBlur = 7;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // Anel energético central no cursor
      const ringRadius = 31 + Math.sin(tick * 2.2) * 1.8;
      ctx.beginPath();
      ctx.arc(mouse.x, mouse.y, ringRadius, 0, Math.PI * 2);
      ctx.fillStyle = '#030917';
      ctx.fill();
      ctx.lineWidth = 2.2;
      ctx.strokeStyle = 'rgba(34, 211, 238, 0.72)';
      ctx.shadowColor = '#22D3EE';
      ctx.shadowBlur = 20;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Partículas orbitando a borda do anel
      for (const rp of ringParticles) {
        rp.angle += rp.speed;
        const r = ringRadius + rp.jitter;
        const rx = mouse.x + Math.cos(rp.angle) * r;
        const ry = mouse.y + Math.sin(rp.angle) * r;
        ctx.beginPath();
        ctx.arc(rx, ry, rp.size, 0, Math.PI * 2);
        ctx.fillStyle = '#67E8F9';
        ctx.shadowColor = '#00E5FF';
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 0,
      }}
    />
  );
};

const darkInputSx = {
  width: '100%',
  px: 1.75,
  py: 1.35,
  borderRadius: '4px',
  bgcolor: '#24324C',
  border: '1px solid rgba(148, 163, 184, 0.18)',
  color: '#F8FAFC',
  fontSize: '0.86rem',
  outline: 'none',
  transition: 'border-color 0.18s ease, box-shadow 0.18s ease',
  '&:focus': {
    borderColor: '#38BDF8',
    boxShadow: '0 0 0 2px rgba(56, 189, 248, 0.18)',
  },
  '&:-webkit-autofill, &:-webkit-autofill:hover, &:-webkit-autofill:focus': {
    WebkitBoxShadow: '0 0 0 1000px #24324C inset !important',
    WebkitTextFillColor: '#F8FAFC !important',
    caretColor: '#F8FAFC !important',
  },
};

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [recaptchaToken, setRecaptchaToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const recaptchaRef = useRef<ReCAPTCHA>(null);
  const navigate = useNavigate();

  const isMounted = useRef(true);
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
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
      await login(username, password, recaptchaToken);
      if (isMounted.current) navigate('/dashboard');
    } catch (err: any) {
      if (isMounted.current) {
        setError(err?.response?.data?.detail || 'Falha no login.');
        try {
          recaptchaRef.current?.reset();
        } catch (_) {}
        setRecaptchaToken(null);
      }
    }
    if (isMounted.current) setLoading(false);
  };

  return (
    <>
      <CssBaseline />
      <Box
        sx={{
          position: 'relative',
          minHeight: '100vh',
          bgcolor: '#030816',
          backgroundImage:
            'radial-gradient(circle at 75% 40%, rgba(14, 165, 233, 0.13), transparent 52%), radial-gradient(circle at 25% 35%, rgba(15, 38, 92, 0.22), transparent 55%)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          overflow: 'hidden',
        }}
      >
        <MouseConstellationCanvas />

        {/* Center Two-Card Stage (Exact Operan Proportions) */}
        <Box
          sx={{
            position: 'relative',
            zIndex: 1,
            flexGrow: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            px: { xs: 2, md: 6 },
            py: 3,
          }}
        >
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: '390px 535px' },
              gap: { xs: 4, md: '96px' },
              alignItems: 'center',
              maxWidth: 1040,
              width: '100%',
            }}
          >
            {/* Left Column: Login Card + Copyright */}
            <Box>
              <Box
                sx={{
                  p: { xs: 3.5, sm: 4.5 },
                  borderRadius: '4px',
                  bgcolor: 'rgba(4, 11, 26, 0.93)',
                  backdropFilter: 'blur(16px)',
                  border: '1px solid rgba(30, 58, 138, 0.38)',
                  boxShadow: '0 28px 65px -15px rgba(0, 0, 0, 0.9)',
                }}
              >
                <Typography
                  sx={{
                    fontSize: '0.66rem',
                    fontWeight: 600,
                    letterSpacing: '0.18em',
                    color: '#38BDF8',
                    textTransform: 'uppercase',
                    mb: 1,
                  }}
                >
                  CONTA / ENTRAR
                </Typography>
                <Typography
                  sx={{
                    fontSize: '1.62rem',
                    fontWeight: 500,
                    color: '#F8FAFC',
                    letterSpacing: '-0.015em',
                    mb: 0.5,
                  }}
                >
                  Bem-vindo de volta
                </Typography>
                <Typography sx={{ fontSize: '0.78rem', color: '#94A3B8', mb: 3.25 }}>
                  Entre para continuar na sua conta.
                </Typography>

                <Box component="form" onSubmit={handleSubmit}>
                  <Stack spacing={2.15}>
                    {/* Username / Email Input */}
                    <Box>
                      <Typography
                        component="label"
                        sx={{ display: 'block', fontSize: '0.76rem', fontWeight: 500, color: '#CBD5E1', mb: 0.75 }}
                      >
                        Endereço de e-mail ou usuário
                      </Typography>
                      <Box
                        component="input"
                        type="text"
                        required
                        value={username}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUsername(e.target.value)}
                        placeholder="usuario@banca.com"
                        sx={darkInputSx}
                      />
                    </Box>

                    {/* Password Input with Mostrar toggle */}
                    <Box>
                      <Typography
                        component="label"
                        sx={{ display: 'block', fontSize: '0.76rem', fontWeight: 500, color: '#CBD5E1', mb: 0.75 }}
                      >
                        Senha
                      </Typography>
                      <Box sx={{ position: 'relative' }}>
                        <Box
                          component="input"
                          type={showPassword ? 'text' : 'password'}
                          required
                          value={password}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
                          placeholder="••••••••••••"
                          sx={{ ...darkInputSx, pr: 7.5 }}
                        />
                        <Button
                          type="button"
                          size="small"
                          onClick={() => setShowPassword((prev) => !prev)}
                          sx={{
                            position: 'absolute',
                            right: 8,
                            top: '50%',
                            transform: 'translateY(-50%)',
                            minWidth: 'auto',
                            px: 0.75,
                            py: 0.2,
                            fontSize: '0.74rem',
                            fontWeight: 600,
                            color: '#38BDF8',
                            textTransform: 'none',
                          }}
                        >
                          {showPassword ? 'Ocultar' : 'Mostrar'}
                        </Button>
                      </Box>
                    </Box>

                    {/* Remember me & Forgot Password */}
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <FormControlLabel
                        control={
                          <Checkbox
                            size="small"
                            checked={rememberMe}
                            onChange={(e) => setRememberMe(e.target.checked)}
                            sx={{ color: '#475569', '&.Mui-checked': { color: '#38BDF8' }, p: 0.5, mr: 0.5 }}
                          />
                        }
                        label={<Typography sx={{ fontSize: '0.74rem', color: '#94A3B8' }}>Lembrar de mim</Typography>}
                        sx={{ m: 0 }}
                      />
                      <Typography
                        component="a"
                        href="#recuperar"
                        onClick={(e: React.MouseEvent) => e.preventDefault()}
                        sx={{
                          fontSize: '0.74rem',
                          color: '#38BDF8',
                          textDecoration: 'none',
                          fontWeight: 500,
                          '&:hover': { textDecoration: 'underline' },
                        }}
                      >
                        Esqueceu a senha?
                      </Typography>
                    </Stack>

                    {/* reCAPTCHA */}
                    <Box sx={{ display: 'flex', justifyContent: 'center', transform: 'scale(0.92)', transformOrigin: 'center' }}>
                      <ReCAPTCHA
                        ref={recaptchaRef}
                        theme="dark"
                        sitekey="6LcTjaorAAAAAOOMZ15DfNDVsLFdqZA-oW1klht4"
                        onChange={(token) => setRecaptchaToken(token)}
                        onExpired={() => setRecaptchaToken(null)}
                      />
                    </Box>

                    {error && (
                      <Alert severity="error" sx={{ fontSize: '0.78rem', py: 0.4 }}>
                        {error}
                      </Alert>
                    )}

                    {/* Gradient Entrar Button */}
                    <Button
                      type="submit"
                      variant="contained"
                      disabled={loading}
                      fullWidth
                      sx={{
                        py: 1.3,
                        borderRadius: '6px',
                        fontSize: '0.88rem',
                        fontWeight: 600,
                        background: 'linear-gradient(90deg, #1E78FF 0%, #05B2DC 100%)',
                        boxShadow: '0 8px 25px -4px rgba(6, 182, 212, 0.5)',
                        '&:hover': {
                          background: 'linear-gradient(90deg, #3B82F6 0%, #22D3EE 100%)',
                          boxShadow: '0 10px 30px -4px rgba(6, 182, 212, 0.7)',
                        },
                      }}
                    >
                      {loading ? <CircularProgress size={20} color="inherit" /> : 'Entrar'}
                    </Button>

                    {/* Create Account Link */}
                    <Typography sx={{ textAlign: 'center', fontSize: '0.76rem', color: '#94A3B8', pt: 0.25 }}>
                      Ainda não tem conta?{' '}
                      <Box
                        component="span"
                        onClick={() => navigate('/register')}
                        sx={{
                          color: '#38BDF8',
                          fontWeight: 600,
                          cursor: 'pointer',
                          '&:hover': { textDecoration: 'underline' },
                        }}
                      >
                        Criar conta
                      </Box>
                    </Typography>
                  </Stack>
                </Box>
              </Box>

              <Typography
                sx={{
                  textAlign: 'center',
                  fontSize: '0.72rem',
                  color: '#64748B',
                  mt: 2.75,
                  letterSpacing: '0.03em',
                }}
              >
                DIAGPRO © 2026 • Todos os direitos reservados
              </Typography>
            </Box>

            {/* Right Column: Hero "Continue daqui." Card (Exact Operan Design) */}
            <Box sx={{ position: 'relative', display: { xs: 'none', md: 'block' } }}>
              {/* Decorative Wireframe Offset Frame */}
              <Box
                sx={{
                  position: 'absolute',
                  top: -28,
                  left: -28,
                  right: 36,
                  bottom: -24,
                  border: '1px solid rgba(56, 189, 248, 0.11)',
                  pointerEvents: 'none',
                }}
              />
              {/* Vertical Guide Line Extending to Bottom */}
              <Box
                sx={{
                  position: 'absolute',
                  top: -28,
                  right: 78,
                  width: '1px',
                  height: '140vh',
                  bgcolor: 'rgba(56, 189, 248, 0.14)',
                  pointerEvents: 'none',
                }}
              />

              <Box
                sx={{
                  position: 'relative',
                  minHeight: 465,
                  p: 6,
                  borderRadius: '64px 4px 4px 4px',
                  background: 'linear-gradient(135deg, #0D2E72 0%, #071942 48%, #040B1D 100%)',
                  border: '1px solid rgba(56, 189, 248, 0.16)',
                  boxShadow: '0 32px 75px -20px rgba(0, 0, 0, 0.92)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  overflow: 'hidden',
                }}
              >
                {/* Segmented Radar Target Graphic in Top-Right (SVG) */}
                <Box
                  sx={{
                    position: 'absolute',
                    top: -28,
                    right: -28,
                    width: 210,
                    height: 210,
                    pointerEvents: 'none',
                    opacity: 0.9,
                  }}
                >
                  <svg width="210" height="210" viewBox="0 0 210 210" fill="none">
                    <circle
                      cx="125"
                      cy="85"
                      r="68"
                      stroke="rgba(56, 189, 248, 0.11)"
                      strokeWidth="22"
                      strokeDasharray="120 45 110 55"
                    />
                    <circle cx="125" cy="85" r="11" fill="rgba(56, 189, 248, 0.14)" />
                  </svg>
                </Box>

                {/* Orbital Dual-Arc Brand Icon (Operan Logo Style) */}
                <Box
                  sx={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    bgcolor: 'rgba(3, 10, 28, 0.75)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5)',
                  }}
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M6 9.5A6.5 6.5 0 0 1 17.5 8"
                      stroke="#38BDF8"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                    />
                    <path
                      d="M18 14.5A6.5 6.5 0 0 1 6.5 16"
                      stroke="#2563EB"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                    />
                    <circle cx="18" cy="8.5" r="1.7" fill="#67E8F9" />
                    <circle cx="6" cy="15.5" r="1.7" fill="#38BDF8" />
                  </svg>
                </Box>

                {/* Center Headline */}
                <Box sx={{ my: 'auto', pt: 4, pb: 2 }}>
                  <Typography
                    sx={{
                      fontSize: '0.68rem',
                      fontWeight: 600,
                      letterSpacing: '0.2em',
                      color: '#38BDF8',
                      textTransform: 'uppercase',
                      mb: 1.5,
                    }}
                  >
                    SUA PRÓXIMA SESSÃO
                  </Typography>
                  <Typography
                    sx={{
                      fontSize: '3.25rem',
                      fontWeight: 600,
                      color: '#FFFFFF',
                      lineHeight: 1.08,
                      letterSpacing: '-0.025em',
                    }}
                  >
                    Continue
                    <br />
                    daqui.
                  </Typography>
                </Box>

                {/* Bottom Status Bar inside Hero Card */}
                <Box>
                  <Box sx={{ height: '1px', bgcolor: 'rgba(148, 163, 184, 0.15)', mb: 2.5 }} />
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography
                      sx={{
                        fontSize: '0.66rem',
                        fontWeight: 500,
                        letterSpacing: '0.2em',
                        color: '#94A3B8',
                        textTransform: 'uppercase',
                      }}
                    >
                      GESTÃO DE CONCURSOS E PROVAS EM REDE
                    </Typography>
                    <Box
                      sx={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        bgcolor: '#10B981',
                        boxShadow: '0 0 12px 2px rgba(16, 185, 129, 0.85)',
                      }}
                    />
                  </Stack>
                </Box>
              </Box>
            </Box>
          </Box>
        </Box>

        {/* Bottom Footer Bar */}
        <Box
          sx={{
            position: 'relative',
            zIndex: 1,
            px: { xs: 2.5, md: 4.5 },
            py: 1.75,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Stack direction="row" spacing={2.5}>
            <Typography
              component="a"
              href="#privacidade"
              onClick={(e: React.MouseEvent) => e.preventDefault()}
              sx={{ fontSize: '0.72rem', color: '#64748B', textDecoration: 'none', '&:hover': { color: '#94A3B8' } }}
            >
              Política de privacidade
            </Typography>
            <Typography
              component="a"
              href="#termos"
              onClick={(e: React.MouseEvent) => e.preventDefault()}
              sx={{ fontSize: '0.72rem', color: '#64748B', textDecoration: 'none', '&:hover': { color: '#94A3B8' } }}
            >
              Termos
            </Typography>
          </Stack>

          <Button
            variant="contained"
            startIcon={<SupportIcon sx={{ fontSize: 18 }} />}
            onClick={() => navigate('/register')}
            sx={{
              borderRadius: '999px',
              px: 2.2,
              py: 0.8,
              fontSize: '0.78rem',
              fontWeight: 600,
              background: 'linear-gradient(90deg, #0284C7 0%, #0EA5E9 100%)',
              boxShadow: '0 4px 20px rgba(14, 165, 233, 0.5)',
            }}
          >
            Precisa de ajuda?
          </Button>
        </Box>
      </Box>
    </>
  );
}
