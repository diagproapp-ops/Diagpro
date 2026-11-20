import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, List,
  ListItemButton, ListItemText, Stack, Tab, Tabs, TextField, ToggleButton, ToggleButtonGroup, Tooltip, Typography,
} from '@mui/material';
import KeyboardIcon from '@mui/icons-material/Keyboard';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CloseIcon from '@mui/icons-material/Close';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import AddPhotoAlternateIcon from '@mui/icons-material/AddPhotoAlternate';
import api from '../../api';
import { erroIA, podeUsar, useStatusIA } from '../ia/iaComum';
import { CATEGORIAS_EQUACAO, paraVisualizar } from './modelosEquacao';

export type EquacaoEmEdicao = { latex: string; bloco: boolean; pos?: number };

type Props = {
  aberta: EquacaoEmEdicao | null;
  onFechar: () => void;
  onConfirmar: (latex: string, bloco: boolean) => void;
  onRemover?: () => void;
};

type Validacao = { estado: 'vazia' | 'conferindo' | 'ok' | 'erro'; erro?: string };

/** Renderiza LaTeX estático dos modelos (constantes do próprio sistema, nunca conteúdo do usuário). */
function Formula({ latex, grande }: { latex: string; grande?: boolean }) {
  const html = useMemo(
    () => katex.renderToString(latex, { throwOnError: false, displayMode: false, strict: false }),
    [latex],
  );
  return <Box component="span" sx={{ fontSize: grande ? 20 : 15, pointerEvents: 'none' }} dangerouslySetInnerHTML={{ __html: html }} />;
}

let configurado = false;

export default function EditorEquacao({ aberta, onFechar, onConfirmar, onRemover }: Props) {
  const [latex, setLatex] = useState('');
  const [bloco, setBloco] = useState(false);
  const [aba, setAba] = useState<'visual' | 'latex'>('visual');
  const [categoria, setCategoria] = useState(CATEGORIAS_EQUACAO[0].id);
  const [validacao, setValidacao] = useState<Validacao>({ estado: 'vazia' });
  const [carregando, setCarregando] = useState(true);
  const campoRef = useRef<any>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const statusIA = useStatusIA();
  const [descricao, setDescricao] = useState('');
  const [ia, setIa] = useState<{ carregando: boolean; explicacao?: string; erro?: string }>({ carregando: false });
  const [imagem, setImagem] = useState<string | null>(null);
  const [arrastando, setArrastando] = useState(false);
  const arquivoRef = useRef<HTMLInputElement>(null);

  // IA: vai só a descrição digitada (e a equação atual, se houver); a resposta passa pela mesma conferência da prova
  const criarComIA = async () => {
    if (!descricao.trim() && !imagem) return;
    setIa({ carregando: true });
    try {
      const corpo = imagem
        ? { imagem, descricao: descricao.trim() }
        : { descricao: descricao.trim(), latex_atual: latex.trim() };
      const { data } = await api.post('/ia/equacao', corpo);
      if (!data.latex) {
        setIa({ carregando: false, erro: data.explicacao || 'A IA não encontrou uma equação na imagem.' });
        return;
      }
      setLatex(data.latex);
      campoRef.current?.setValue(data.latex, { silenceNotifications: true });
      setIa({ carregando: false, explicacao: data.explicacao });
    } catch (err) {
      setIa({ carregando: false, erro: erroIA(err) });
    }
  };

  // Foto/print da equação: reduzida no navegador (máx. 1600 px, JPEG) antes de sair do computador;
  // redesenhar no canvas também descarta os metadados da foto (ex.: localização do celular).
  const receberImagem = async (arquivo: File | null | undefined) => {
    if (!arquivo) return;
    if (!/^image\/(png|jpeg|webp)$/.test(arquivo.type)) {
      setIa({ carregando: false, erro: 'Use uma imagem PNG, JPG ou WEBP.' });
      return;
    }
    if (arquivo.size > 25 * 1024 * 1024) {
      setIa({ carregando: false, erro: 'Imagem grande demais (máximo 25 MB).' });
      return;
    }
    try {
      // 'from-image' endireita foto de celular (a definição de tipos do TS ainda não conhece o valor)
      const bitmap = await createImageBitmap(arquivo, { imageOrientation: 'from-image' } as unknown as ImageBitmapOptions);
      const escala = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(bitmap.width * escala);
      canvas.height = Math.round(bitmap.height * escala);
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('canvas');
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      bitmap.close();
      setImagem(canvas.toDataURL('image/jpeg', 0.9));
      setIa({ carregando: false });
    } catch {
      setIa({ carregando: false, erro: 'Não foi possível abrir a imagem.' });
    }
  };

  const colarImagem = (ev: React.ClipboardEvent) => {
    const item = Array.from(ev.clipboardData?.items || []).find((i) => i.type.startsWith('image/'));
    if (item && podeUsar(statusIA, 'equacao_imagem')) {
      ev.preventDefault();
      receberImagem(item.getAsFile());
    }
  };

  // ao abrir: estado inicial
  useEffect(() => {
    if (!aberta) return;
    setLatex(aberta.latex || '');
    setBloco(aberta.bloco);
    setAba('visual');
    setValidacao({ estado: aberta.latex ? 'conferindo' : 'vazia' });
    setDescricao('');
    setIa({ carregando: false });
    setImagem(null);
  }, [aberta]);

  // campo visual (MathLive), carregado só quando o criador abre
  const montarCampo = useCallback((host: HTMLDivElement | null) => {
    hostRef.current = host;
    if (!host || !aberta) return;
    let cancelado = false;
    setCarregando(true);
    import('mathlive').then(({ MathfieldElement }) => {
      if (cancelado || !hostRef.current) return;
      if (!configurado) {
        // fontes servidas pelo próprio DiagPro (nada de CDN externo); sem sons
        MathfieldElement.fontsDirectory = '/mathlive/fonts';
        MathfieldElement.soundsDirectory = null;
        MathfieldElement.locale = 'pt';
        // teclado virtual acima das janelas do editor (que ficam em z-index 1300–1700)
        document.documentElement.style.setProperty('--keyboard-zindex', '3000');
        configurado = true;
      }
      const mf: any = new MathfieldElement();
      mf.mathVirtualKeyboardPolicy = 'manual';
      mf.smartFence = true;
      mf.style.width = '100%';
      mf.style.fontSize = '26px';
      mf.style.padding = '10px 12px';
      mf.style.borderRadius = '10px';
      mf.style.border = '1px solid rgba(56, 189, 248, 0.45)';
      mf.style.background = '#FFFFFF';
      mf.style.color = '#0F172A';
      mf.setAttribute('aria-label', 'Equação');
      mf.value = aberta.latex || '';
      mf.addEventListener('input', () => setLatex(mf.getValue('latex-expanded')));
      hostRef.current.innerHTML = '';
      hostRef.current.appendChild(mf);
      campoRef.current = mf;
      setCarregando(false);
      setTimeout(() => mf.focus(), 50);
    });
    return () => {
      cancelado = true;
    };
  }, [aberta]);

  // fechar: esconde o teclado virtual e solta o campo
  useEffect(() => {
    if (aberta) return;
    (window as any).mathVirtualKeyboard?.hide?.();
    campoRef.current = null;
  }, [aberta]);

  // confere no servidor (mesma conversão da exportação) se a equação vai sair na prova
  useEffect(() => {
    if (!aberta) return;
    const texto = latex.trim();
    if (!texto) {
      setValidacao({ estado: 'vazia' });
      return;
    }
    setValidacao({ estado: 'conferindo' });
    const t = setTimeout(async () => {
      try {
        const { data } = await api.post('/editor/equacao/validar', { latex: texto });
        setValidacao(data.ok ? { estado: 'ok' } : { estado: 'erro', erro: data.erro });
      } catch {
        setValidacao({ estado: 'erro', erro: 'Não foi possível conferir a equação agora. Tente de novo.' });
      }
    }, 350);
    return () => clearTimeout(t);
  }, [latex, aberta]);

  const inserirModelo = (modelo: string) => {
    const mf = campoRef.current;
    if (aba === 'latex' || !mf) {
      setLatex((atual) => `${atual}${atual && !atual.endsWith(' ') ? ' ' : ''}${modelo.replace(/#\?/g, '{}')}`);
      return;
    }
    mf.insert(modelo, { format: 'latex', selectionMode: 'placeholder', focus: true });
    setLatex(mf.getValue('latex-expanded'));
  };

  const trocarAba = (nova: 'visual' | 'latex') => {
    setAba(nova);
    const mf = campoRef.current;
    if (nova === 'visual' && mf) {
      mf.setValue(latex, { silenceNotifications: true });
      setTimeout(() => mf.focus(), 30);
    }
  };

  const confirmar = () => {
    if (validacao.estado !== 'ok') return;
    onConfirmar(latex.trim(), bloco);
  };

  const cat = CATEGORIAS_EQUACAO.find((c) => c.id === categoria) || CATEGORIAS_EQUACAO[0];

  return (
    <Dialog
      open={!!aberta}
      onClose={onFechar}
      maxWidth="lg"
      fullWidth
      disableEnforceFocus // o teclado virtual de equações fica fora do diálogo
      sx={{ zIndex: 1700 }}
      PaperProps={{ sx: { height: { md: '88vh' } } }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 2, pr: 6 }}>
        {aberta?.pos !== undefined ? 'Editar equação' : 'Nova equação'}
        <ToggleButtonGroup size="small" exclusive value={bloco ? 'bloco' : 'linha'} onChange={(_, v) => v && setBloco(v === 'bloco')}>
          <ToggleButton value="linha">Na linha do texto</ToggleButton>
          <ToggleButton value="bloco">Em destaque (centralizada)</ToggleButton>
        </ToggleButtonGroup>
        <IconButton aria-label="Fechar" onClick={onFechar} sx={{ position: 'absolute', right: 12, top: 12 }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers sx={{ display: 'flex', gap: 2, p: 0, overflow: 'hidden' }}>
        {/* categorias */}
        <List dense sx={{ width: 220, flexShrink: 0, overflowY: 'auto', borderRight: '1px solid', borderColor: 'divider', py: 0 }}>
          {CATEGORIAS_EQUACAO.map((c) => (
            <ListItemButton key={c.id} selected={c.id === categoria} onClick={() => setCategoria(c.id)}>
              <ListItemText primary={c.nome} secondary={`${c.modelos.length} modelos`} />
            </ListItemButton>
          ))}
        </List>

        <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', p: 2, gap: 1.5, overflowY: 'auto' }}>
          {(podeUsar(statusIA, 'equacao') || podeUsar(statusIA, 'equacao_imagem')) && (
            <Box
              sx={{ p: 1.5, borderRadius: 2, border: '1px dashed', borderColor: arrastando ? 'primary.main' : 'secondary.main',
                bgcolor: arrastando ? 'rgba(56, 189, 248, 0.08)' : 'transparent' }}
              onDragOver={(e) => { if (podeUsar(statusIA, 'equacao_imagem')) { e.preventDefault(); setArrastando(true); } }}
              onDragLeave={() => setArrastando(false)}
              onDrop={(e) => { e.preventDefault(); setArrastando(false); if (podeUsar(statusIA, 'equacao_imagem')) receberImagem(e.dataTransfer.files?.[0]); }}
            >
              {imagem && (
                <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1 }}>
                  <Box component="img" src={imagem} alt="Imagem da equação enviada"
                    sx={{ maxHeight: 110, maxWidth: 260, borderRadius: 1, border: '1px solid', borderColor: 'divider', bgcolor: '#fff' }} />
                  <Box>
                    <Typography variant="body2">A IA vai transcrever a equação desta imagem.</Typography>
                    <Button size="small" color="inherit" onClick={() => setImagem(null)}>Remover imagem</Button>
                  </Box>
                </Stack>
              )}
              <Stack direction="row" spacing={1} alignItems="center">
                {podeUsar(statusIA, 'equacao_imagem') && !imagem && (
                  <Tooltip title="Foto ou print da equação (vale escrita à mão). Também dá para colar (Ctrl+V) ou arrastar a imagem aqui." arrow>
                    <Button variant="outlined" color="secondary" startIcon={<AddPhotoAlternateIcon />} onClick={() => arquivoRef.current?.click()}
                      sx={{ whiteSpace: 'nowrap' }}>
                      Enviar imagem
                    </Button>
                  </Tooltip>
                )}
                <input ref={arquivoRef} type="file" accept="image/png,image/jpeg,image/webp" hidden aria-label="Imagem da equação"
                  onChange={(e) => { receberImagem(e.target.files?.[0]); e.target.value = ''; }} />
                <TextField
                  size="small" fullWidth value={descricao} onChange={(e) => setDescricao(e.target.value)}
                  onPaste={colarImagem}
                  placeholder={imagem ? 'Observação opcional (ex.: é a equação de baixo)' : latex ? 'Diga o que mudar (ex.: troque o expoente por 3)'
                    : podeUsar(statusIA, 'equacao') ? 'Descreva a equação (ex.: fórmula de Bhaskara) ou cole uma imagem' : 'Envie ou cole a imagem da equação'}
                  inputProps={{ 'aria-label': 'Descrição da equação para a IA', maxLength: 1000 }}
                  disabled={!imagem && !podeUsar(statusIA, 'equacao')}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); criarComIA(); } }}
                />
                <Button variant="contained" color="secondary" startIcon={ia.carregando ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeIcon />}
                  disabled={ia.carregando || (!descricao.trim() && !imagem)} onClick={criarComIA} sx={{ whiteSpace: 'nowrap' }}>
                  {imagem ? 'Ler imagem com IA' : latex ? 'Ajustar com IA' : 'Criar com IA'}
                </Button>
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                {imagem
                  ? 'Vai para a IA só esta imagem (reduzida e sem os dados da foto) e a observação. Escrita à mão pode ser ambígua: confira antes de inserir.'
                  : `Vai para a IA só o que você escrever aqui${latex ? ' e a equação atual' : ''}. Confira o resultado antes de inserir.`}
              </Typography>
              {ia.explicacao && <Typography variant="body2" sx={{ mt: 0.5 }}>{ia.explicacao}</Typography>}
              {ia.erro && <Alert severity="error" sx={{ mt: 1 }}>{ia.erro}</Alert>}
            </Box>
          )}
          {/* modelos da categoria */}
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{cat.nome}</Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(92px, 1fr))', gap: 0.75 }}>
              {cat.modelos.map((mod) => (
                <Tooltip key={mod.latex + mod.titulo} title={mod.titulo} arrow>
                  <Button
                    variant="outlined"
                    color="inherit"
                    aria-label={mod.titulo}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => inserirModelo(mod.latex)}
                    sx={{ minHeight: 48, textTransform: 'none', borderColor: 'divider', overflow: 'hidden', px: 0.5 }}
                  >
                    <Formula latex={paraVisualizar(mod.latex)} />
                  </Button>
                </Tooltip>
              ))}
            </Box>
          </Box>

          {/* edição */}
          <Box>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Tabs value={aba} onChange={(_, v) => trocarAba(v)} sx={{ minHeight: 36, flex: 1 }}>
                <Tab value="visual" label="Visual" sx={{ minHeight: 36 }} />
                <Tab value="latex" label="LaTeX" sx={{ minHeight: 36 }} />
              </Tabs>
              {aba === 'visual' && (
                <Button size="small" startIcon={<KeyboardIcon />} onClick={() => {
                  campoRef.current?.focus();
                  (window as any).mathVirtualKeyboard?.show?.();
                }}>
                  Teclado de símbolos
                </Button>
              )}
            </Stack>
            <Box sx={{ display: aba === 'visual' ? 'block' : 'none', mt: 1 }}>
              {carregando && <CircularProgress size={22} sx={{ m: 1 }} />}
              <div ref={montarCampo} />
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.75 }}>
                Digite direto: "/" faz fração, "^" expoente, "_" índice, "sqrt" raiz, "pi" π, "alpha" α, "&gt;=" ≥.
                Tab passa para a próxima lacuna.
              </Typography>
            </Box>
            {aba === 'latex' && (
              <TextField
                value={latex}
                onChange={(e) => setLatex(e.target.value)}
                multiline
                minRows={4}
                fullWidth
                autoFocus
                placeholder="Ex.: x=\frac{-b\pm\sqrt{b^2-4ac}}{2a}"
                inputProps={{ 'aria-label': 'LaTeX da equação', spellCheck: false, style: { fontFamily: 'Consolas, monospace', fontSize: 15 } }}
                sx={{ mt: 1 }}
              />
            )}
          </Box>

          {/* como vai ficar + conferência da prova */}
          {aba === 'latex' && latex.trim() && (
            <Box sx={{ p: 2, borderRadius: 2, bgcolor: '#FFFFFF', color: '#0F172A', textAlign: bloco ? 'center' : 'left' }}>
              <Formula latex={latex} grande />
            </Box>
          )}
          {validacao.estado === 'ok' && (
            <Alert icon={<CheckCircleIcon fontSize="inherit" />} severity="success">
              Pronta para a prova: sai como equação do Word (editável) e no PDF.
            </Alert>
          )}
          {validacao.estado === 'erro' && <Alert severity="warning">{validacao.erro}</Alert>}
          {validacao.estado === 'conferindo' && (
            <Typography variant="body2" color="text.secondary">Conferindo se a equação sai na prova…</Typography>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        {onRemover && aberta?.pos !== undefined && (
          <Button color="error" onClick={onRemover} sx={{ mr: 'auto' }}>Remover equação</Button>
        )}
        <Button onClick={onFechar}>Cancelar</Button>
        <Button variant="contained" onClick={confirmar} disabled={validacao.estado !== 'ok'}>
          {aberta?.pos !== undefined ? 'Atualizar' : 'Inserir'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
