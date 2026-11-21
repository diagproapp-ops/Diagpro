import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Paper, Stack,
  Table, TableBody, TableCell, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import ListAltOutlinedIcon from '@mui/icons-material/ListAltOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import api from '../../api';

type CampoGuia = { grupo: string; campo: string; descricao: string; exemplo: string; origem: 'automatico' | 'em_branco' };
type Previa = {
  legado: boolean; mensagem?: string; imagem?: string; sem_formulario?: boolean; preenchida?: boolean;
  campos_no_pdf?: string[]; reconhecidos?: string[]; desconhecidos?: string[];
};

function erroDaApi(e: any, padrao: string) {
  const d = e?.response?.data?.detail;
  return typeof d === 'string' ? d : padrao;
}

// Capa do cargo: prévia preenchida (mesmo preenchimento da exportação, com dados de exemplo) e guia dos campos.
const CapaDoCargo: React.FC<{
  eventId: string;
  refCapa: string;
  cargo: { nome_cargo?: string; codigo_cargo?: string; nivel?: string; turno?: string };
  onImportar: () => void;
}> = ({ eventId, refCapa, cargo, onImportar }) => {
  const [previa, setPrevia] = useState<Previa | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ampliada, setAmpliada] = useState(false);
  const [guiaAberto, setGuiaAberto] = useState(false);
  const [guia, setGuia] = useState<CampoGuia[] | null>(null);
  const [copiado, setCopiado] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    if (!refCapa) { setPrevia(null); return; }
    setCarregando(true);
    setErro(null);
    try {
      const { data } = await api.post(`/eventos/${eventId}/cargos/capa/previa`, {
        ref: refCapa, nome_cargo: cargo.nome_cargo || null, codigo_cargo: cargo.codigo_cargo || null,
        nivel: cargo.nivel || null, turno: cargo.turno || null,
      }, { timeout: 120000 });
      setPrevia(data);
    } catch (e: any) {
      setPrevia(null);
      setErro(erroDaApi(e, 'Não foi possível mostrar a capa.'));
    } finally {
      setCarregando(false);
    }
    // a prévia acompanha o arquivo; nome/código do cargo entram ao clicar em "Atualizar prévia"
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId, refCapa]);
  useEffect(() => { carregar(); }, [carregar]);

  const abrirGuia = async () => {
    setGuiaAberto(true);
    if (!guia) {
      try { setGuia((await api.get('/cargos/capa/guia')).data.campos); } catch { setGuia([]); }
    }
  };
  const noPdf = useMemo(() => new Set(previa?.campos_no_pdf || []), [previa]);
  const grupos = useMemo(() => Array.from(new Set((guia || []).map(g => g.grupo))), [guia]);
  const copiar = (nome: string) => { navigator.clipboard?.writeText(nome); setCopiado(nome); setTimeout(() => setCopiado(null), 1500); };

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 2 }}>
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2.5} alignItems={{ md: 'flex-start' }}>
        <Box sx={{ width: { xs: '100%', md: 220 }, flexShrink: 0 }}>
          {carregando ? (
            <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: 'action.hover', borderRadius: 1 }}>
              <CircularProgress size={28} />
            </Box>
          ) : previa?.imagem ? (
            <Tooltip title="Clique para ampliar">
              <Box component="img" src={previa.imagem} alt="Prévia da capa" onClick={() => setAmpliada(true)}
                sx={{ width: '100%', borderRadius: 1, boxShadow: 3, cursor: 'zoom-in', bgcolor: '#fff', display: 'block' }} />
            </Tooltip>
          ) : (
            <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', p: 2,
              border: '1px dashed', borderColor: 'divider', borderRadius: 1, color: 'text.secondary' }}>
              <Typography variant="body2">{refCapa ? 'Sem prévia' : 'Nenhuma capa importada'}</Typography>
            </Box>
          )}
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography fontWeight={800}>Capa da prova</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            PDF com campos de formulário. Na exportação o DiagPro preenche cada campo pelo nome (veja o guia) para cada tipo de
            prova. A prévia usa o mesmo preenchimento, com dados de exemplo.
          </Typography>
          {erro && <Alert severity="error" sx={{ mb: 1.5 }}>{erro}</Alert>}
          {previa?.legado && <Alert severity="warning" sx={{ mb: 1.5 }}>{previa.mensagem}</Alert>}
          {previa && !previa.legado && previa.sem_formulario && (
            <Alert severity="warning" sx={{ mb: 1.5 }}>
              Este PDF não tem campos de formulário: ele sai como está, sem nenhum dado preenchido. Crie os campos com os nomes do guia.
            </Alert>
          )}
          {previa && !previa.legado && !previa.sem_formulario && (
            <Box sx={{ mb: 1.5 }}>
              <Typography variant="caption" color="text.secondary" fontWeight={700}>CAMPOS ENCONTRADOS NESTE PDF</Typography>
              <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', rowGap: 0.75, mt: 0.5 }}>
                {(previa.reconhecidos || []).map(c => <Chip key={c} size="small" color="success" variant="outlined" label={c} />)}
                {(previa.desconhecidos || []).map(c => (
                  <Tooltip key={c} title="O DiagPro não conhece este nome: o campo sai em branco. Confira no guia.">
                    <Chip size="small" color="warning" variant="outlined" label={`${c} (desconhecido)`} />
                  </Tooltip>
                ))}
              </Stack>
            </Box>
          )}
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
            <Button size="small" variant="outlined" color="secondary" startIcon={<UploadFileIcon />} onClick={onImportar}>
              {refCapa ? 'Trocar PDF de capa' : 'Importar PDF de capa'}
            </Button>
            <Button size="small" variant="outlined" startIcon={<ListAltOutlinedIcon />} onClick={abrirGuia}>Campos da capa (guia)</Button>
            {refCapa && !previa?.legado && (
              <Button size="small" startIcon={<RefreshIcon />} onClick={carregar} disabled={carregando}>Atualizar prévia</Button>
            )}
          </Stack>
        </Box>
      </Stack>

      <Dialog open={ampliada} onClose={() => setAmpliada(false)} maxWidth="md">
        <DialogTitle>Capa como sai na prova (dados de exemplo)</DialogTitle>
        <DialogContent>
          {previa?.imagem && <Box component="img" src={previa.imagem} alt="Capa ampliada" sx={{ width: '100%', maxWidth: 760, bgcolor: '#fff', display: 'block' }} />}
        </DialogContent>
        <DialogActions><Button onClick={() => setAmpliada(false)}>Fechar</Button></DialogActions>
      </Dialog>

      <Dialog open={guiaAberto} onClose={() => setGuiaAberto(false)} maxWidth="md" fullWidth>
        <DialogTitle>Campos da capa</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            Monte a capa no Word/LibreOffice/Acrobat e exporte como <b>PDF com formulário</b>. Em cada lugar onde um dado deve
            aparecer, crie um <b>campo de texto</b> com o nome <b>exatamente</b> como na coluna Campo (maiúsculas e minúsculas
            contam). Clique no nome para copiar.
          </Alert>
          {!guia ? <CircularProgress size={24} /> : grupos.map(g => (
            <Box key={g} sx={{ mb: 2 }}>
              <Typography fontWeight={800} sx={{ mb: 0.5 }}>{g}</Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Campo</TableCell><TableCell>O que entra</TableCell><TableCell>Exemplo</TableCell><TableCell>Preenchimento</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {guia.filter(c => c.grupo === g).map(c => (
                    <TableRow key={c.campo} hover>
                      <TableCell>
                        <Tooltip title={copiado === c.campo ? 'Copiado!' : 'Copiar o nome'}>
                          <Button size="small" onClick={() => copiar(c.campo)} endIcon={<ContentCopyIcon sx={{ fontSize: 14 }} />}
                            sx={{ fontFamily: 'monospace', textTransform: 'none', fontWeight: 700 }}>
                            {c.campo}
                          </Button>
                        </Tooltip>
                        {noPdf.has(c.campo) && <Chip size="small" color="success" label="no PDF" sx={{ ml: 0.5 }} />}
                      </TableCell>
                      <TableCell>{c.descricao}</TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>{c.exemplo || '—'}</TableCell>
                      <TableCell>
                        {c.origem === 'automatico'
                          ? <Chip size="small" color="success" variant="outlined" label="Automático" />
                          : <Tooltip title="O DiagPro deixa em branco (para preencher à mão ou pela gráfica)"><Chip size="small" variant="outlined" label="Em branco" /></Tooltip>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          ))}
          <Divider sx={{ my: 1 }} />
          <Typography variant="caption" color="text.secondary">
            Cada tipo de prova (PADRÃO, Tipo A, B...) recebe uma capa própria com o tipo e a frase daquele tipo. Campos com nomes
            que não estão aqui saem em branco.
          </Typography>
        </DialogContent>
        <DialogActions><Button variant="contained" onClick={() => setGuiaAberto(false)}>Fechar</Button></DialogActions>
      </Dialog>
    </Paper>
  );
};

export default CapaDoCargo;
