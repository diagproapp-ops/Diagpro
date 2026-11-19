import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Paper, Divider, Button, Stack, CircularProgress,
  Snackbar, Alert, FormControl, InputLabel, Select, MenuItem,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField
} from '@mui/material';
import Layout from '../components/Layout';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';

type Cargo = {
  id_cargo: string;
  nome_cargo: string;
  codigo_cargo?: string;
};

type GabaritoQuestao = {
  numero_questao: string | number;
  disciplina: string;
  letra_correta: string;
  texto_correto: string;
  codigo_curto: string;
  tipo_prova?: string; // novo campo
};

const GabaritoPage: React.FC = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();

  const [cargos, setCargos] = useState<Cargo[]>([]);
  const [carregandoCargos, setCarregandoCargos] = useState(true);
  const [cargo, setCargo] = useState('');
  const [gabarito, setGabarito] = useState<GabaritoQuestao[]>([]);
  const [carregandoGabarito, setCarregandoGabarito] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean, message: string, severity: "success" | "error" | "info" }>({ open: false, message: '', severity: "success" });

  // Senha do evento: o gabarito só aparece para quem a informa (fica só em memória, nunca na URL)
  const [senhaEvento, setSenhaEvento] = useState('');
  const [senhaLiberada, setSenhaLiberada] = useState('');
  const comSenha = { headers: { 'X-Senha-Evento': senhaLiberada } };
  const tratarErroGabarito = (err: any, padrao: string) => {
    const status = err?.response?.status;
    const det = err?.response?.data?.detail;
    if (status === 403 || status === 429) {
      setSenhaLiberada('');
      setGabarito([]);
      setSnackbar({ open: true, message: det || "Senha do evento inválida.", severity: "error" });
    } else if (status === 409 && det && typeof det === 'object') {
      // prova com problema (ex.: questão sem alternativa correta): o gabarito sairia errado
      const lista = (det.verificacao || []).flatMap((v: any) => v.bloqueios.map((b: any) =>
        `${v.cargo}: questão ${b.questao ?? '-'} (${b.codigo}) — ${b.problema}`));
      setGabarito([]);
      setSnackbar({ open: true, message: [det.mensagem, ...lista.slice(0, 5)].join(' | '), severity: "error" });
    } else {
      setSnackbar({ open: true, message: padrao, severity: "error" });
    }
  };

  // Exportação ZIP
  const [exportarZipModalOpen, setExportarZipModalOpen] = useState(false);
  const [senhaZip, setSenhaZip] = useState('');
  const [exportSnackbar, setExportSnackbar] = useState<{ open: boolean, message: string, severity: "success" | "error" }>({ open: false, message: '', severity: "success" });

  // Filtros
  const [variacoes, setVariacoes] = useState<string[]>([]);
  const [tipoProva, setTipoProva] = useState("PADRÃO");
  const [disciplinas, setDisciplinas] = useState<string[]>([]);
  const [filtroDisciplina, setFiltroDisciplina] = useState<string>("");
  const [filtroCodigoCurto, setFiltroCodigoCurto] = useState<string>("");

  // Buscar cargos do evento
  useEffect(() => {
    async function fetchCargos() {
      setCarregandoCargos(true);
      try {
        const res = await api.get(`/eventos/${eventId}/cargos`);
        setCargos(res.data);
      } catch {
        setSnackbar({ open: true, message: "Erro ao carregar cargos", severity: "error" });
      }
      setCarregandoCargos(false);
    }
    fetchCargos();
  }, [eventId]);

  // Buscar variações ao selecionar cargo
  useEffect(() => {
    if (!cargo) {
      setVariacoes([]);
      setTipoProva("PADRÃO");
      return;
    }
    api.get(`/api/gabarito/eventos/${eventId}/cargos/${cargo}/variacoes`)
      .then(res => {
        const variacoesApi = Array.isArray(res.data) ? res.data.filter((v): v is string => typeof v === "string") : [];
        setVariacoes(variacoesApi);
        setTipoProva(variacoesApi.length > 0 ? variacoesApi[0] : "PADRÃO");
      })
      .catch(() => {
        setVariacoes(["PADRÃO"]);
        setTipoProva("PADRÃO");
      });
  }, [cargo, eventId]);

  // Buscar o gabarito para o cargo/tipoProva selecionado OU buscar todos quando filtra por código curto
  useEffect(() => {
    if (!cargo || !senhaLiberada) {
      setGabarito([]);
      setDisciplinas([]);
      return;
    }
    setCarregandoGabarito(true);

    if (!filtroCodigoCurto) {
      // Busca normal, por variação
      api
        .get(`/api/gabarito/eventos/${eventId}/cargos/${cargo}/gabarito?tipo_prova=${encodeURIComponent(tipoProva)}`, comSenha)
        .then(res => {
          setGabarito(res.data);
          const dists = Array.from(
            new Set(
              (Array.isArray(res.data) ? res.data : [])
                .map((q: any) => typeof q.disciplina === "string" ? q.disciplina : "")
                .filter(Boolean)
            )
          );
          setDisciplinas(dists);
        })
        .catch(err => tratarErroGabarito(err, "Erro ao buscar gabarito."))
        .finally(() => setCarregandoGabarito(false));
    } else {
      // Busca de todas as variações, filtra pelo código curto
      api.get(`/api/gabarito/eventos/${eventId}/cargos/${cargo}/variacoes`)
      .then(res => {
        const variacoesApi = Array.isArray(res.data) ? res.data.filter((v: any): v is string => typeof v === "string") : [];
        Promise.all(
          variacoesApi.map(v =>
            api
              .get(`/api/gabarito/eventos/${eventId}/cargos/${cargo}/gabarito?tipo_prova=${encodeURIComponent(v)}`, comSenha)
              .then(res2 => 
                Array.isArray(res2.data)
                  ? res2.data.map((q: any) => ({ ...q, tipo_prova: v })) // garante o campo tipo_prova
                  : []
              )
              .catch(() => [])
          )
        ).then(allResults => {
          const todasQuestoes = allResults.flat();
          const filtradas = todasQuestoes.filter((q: any) =>
            q.codigo_curto && q.codigo_curto.toLowerCase().includes(filtroCodigoCurto.toLowerCase())
          );
          setGabarito(filtradas);
          const dists = Array.from(
            new Set(
              (filtradas)
                .map((q: any) => typeof q.disciplina === "string" ? q.disciplina : "")
                .filter(Boolean)
            )
          );
          setDisciplinas(dists);
          setCarregandoGabarito(false);
        });
      })
      .catch(() => {
        setGabarito([]);
        setDisciplinas([]);
        setCarregandoGabarito(false);
        setSnackbar({ open: true, message: "Erro ao buscar variações para filtrar por código curto.", severity: "error" });
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cargo, eventId, tipoProva, filtroCodigoCurto, senhaLiberada]);

  // Exportar ZIP com senha
  const handleExportarZip = async () => {
    try {
      if (!senhaZip) {
        setExportSnackbar({ open: true, message: "Digite a senha do evento.", severity: "error" });
        return;
      }
      const response = await api.post(
        `/api/gabarito/eventos/${eventId}/exportar-gabaritos-zip`,
        null,
        { headers: { 'X-Senha-Evento': senhaZip }, responseType: 'blob' }
      );
      const blob = new Blob([response.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `GABARITOS_EVENTO_${eventId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setExportarZipModalOpen(false);
      setExportSnackbar({ open: true, message: "Gabarito exportado com sucesso!", severity: "success" });
    } catch (e: any) {
      let detalhe = "Senha inválida ou erro ao exportar.";
      try {
        const corpo = e?.response?.data;
        const info = corpo instanceof Blob ? JSON.parse(await corpo.text()) : corpo;
        const det = info?.detail;
        if (det && typeof det === 'object') {
          const lista = (det.verificacao || []).flatMap((v: any) => v.bloqueios.map((b: any) =>
            `${v.cargo}: questão ${b.questao ?? '-'} (${b.codigo}) — ${b.problema}`));
          detalhe = [det.mensagem, ...lista.slice(0, 5)].join(' | ');
        } else {
          detalhe = det || detalhe;
        }
      } catch { /* mantém a mensagem genérica */ }
      setExportSnackbar({ open: true, message: detalhe, severity: "error" });
    } finally {
      setSenhaZip('');
    }
  };

  // Filtro aplicado ao gabarito
  const gabaritoFiltrado = !filtroDisciplina
    ? gabarito
    : gabarito.filter(q => q.disciplina === filtroDisciplina);

  return (
    <Layout>
      <Paper sx={{ p: { xs: 2, md: 4 }, borderRadius: 5, boxShadow: 3 }}>
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 2,
          flexWrap: 'wrap',
          gap: 2
        }}>
          <Typography variant="h5" fontWeight="bold" color="primary.dark">
            Gabaritos de Múltipla Escolha
          </Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              color="secondary"
              onClick={() => navigate(-1)}
              sx={{ borderRadius: 2, fontWeight: 'bold' }}
            >
              Voltar
            </Button>
            <Button
              variant="contained"
              color="primary"
              onClick={() => setExportarZipModalOpen(true)}
              sx={{ borderRadius: 2, fontWeight: 'bold', minWidth: 180 }}
            >
              Exportar Gabarito
            </Button>
          </Box>
        </Box>
        <Divider sx={{ mb: 3 }} />

        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center" sx={{ mb: 2 }}>
          {senhaLiberada ? (
            <>
              <Alert severity="success" sx={{ flex: 1, py: 0 }}>Gabarito liberado com a senha do evento.</Alert>
              <Button variant="outlined" onClick={() => { setSenhaLiberada(''); setSenhaEvento(''); }}>
                Bloquear
              </Button>
            </>
          ) : (
            <>
              <TextField
                label="Senha do evento"
                type="password"
                size="small"
                value={senhaEvento}
                onChange={e => setSenhaEvento(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && senhaEvento) { setSenhaLiberada(senhaEvento); setSenhaEvento(''); } }}
                autoComplete="off"
                sx={{ flex: 1 }}
              />
              <Button
                variant="contained"
                disabled={!senhaEvento}
                onClick={() => { setSenhaLiberada(senhaEvento); setSenhaEvento(''); }}
              >
                Liberar gabarito
              </Button>
            </>
          )}
        </Stack>

        <Stack direction={{ xs: "column", sm: "row" }} spacing={3} alignItems="center" sx={{ mb: 3 }}>
          <FormControl fullWidth size="small" disabled={carregandoCargos}>
            <InputLabel id="cargo-label">Cargo</InputLabel>
            <Select
              labelId="cargo-label"
              value={cargo}
              label="Cargo"
              onChange={e => setCargo(e.target.value as string)}
            >
              {cargos.map(c => (
                <MenuItem key={c.id_cargo} value={c.id_cargo}>
                  {[c.codigo_cargo, c.nome_cargo].filter(Boolean).join(' - ')}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {/* Select para variação */}
          {!filtroCodigoCurto && variacoes.length > 1 && (
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel id="variacao-label">Variação</InputLabel>
              <Select
                labelId="variacao-label"
                value={tipoProva}
                label="Variação"
                onChange={e => setTipoProva(e.target.value as string)}
              >
                {variacoes.map(v => (
                  <MenuItem key={v} value={v}>{v}</MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          {/* Select para disciplina */}
          {disciplinas.length > 1 && (
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel id="disciplina-label">Filtrar Disciplina</InputLabel>
              <Select
                labelId="disciplina-label"
                value={filtroDisciplina}
                label="Filtrar Disciplina"
                onChange={e => setFiltroDisciplina(e.target.value as string)}
              >
                <MenuItem value="">Todas</MenuItem>
                {disciplinas.map(d => (
                  <MenuItem key={d} value={d}>{d}</MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          {/* Filtro código curto */}
          <TextField
            label="Filtrar Código Curto"
            value={filtroCodigoCurto}
            onChange={e => setFiltroCodigoCurto(e.target.value)}
            size="small"
            sx={{ minWidth: 180 }}
          />
        </Stack>

        {carregandoGabarito ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress size={32} />
          </Box>
        ) : gabaritoFiltrado.length === 0 ? (
          <Typography color="text.secondary" align="center" sx={{ mt: 6 }}>
            {!senhaLiberada
              ? "Informe a senha do evento para ver o gabarito."
              : cargo ? "Nenhum gabarito disponível para este filtro." : "Selecione um cargo para ver o gabarito."}
          </Typography>
        ) : (
          <Box sx={{ overflowX: "auto" }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.45)', textAlign: 'center'}}>Tipo Prova</th>
                  <th style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.45)', textAlign: 'center'}}>Questão</th>
                  <th style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.45)', textAlign: 'center'}}>Disciplina</th>
                  <th style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.45)', textAlign: 'center'}}>Letra</th>
                  <th style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.45)'}}>Alternativa Correta</th>
                  <th style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.45)', textAlign: 'center'}}>Código Curto</th>
                </tr>
              </thead>
              <tbody>
                {gabaritoFiltrado.map((q, idx) => (
                  <tr key={idx}>
                    <td style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.25)', textAlign: 'center'}}>{q.tipo_prova}</td>
                    <td style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.25)', textAlign: 'center'}}>{q.numero_questao}</td>
                    <td style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.25)', textAlign: 'center'}}>{q.disciplina}</td>
                    <td style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.25)', textAlign: 'center'}}>{q.letra_correta}</td>
                    <td style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.25)', maxWidth: 300, wordBreak: 'break-word'}}>{q.texto_correto}</td>
                    <td style={{padding: 8, borderBottom:'1px solid rgba(148, 163, 184, 0.25)', textAlign: 'center'}}>{q.codigo_curto}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Box>
        )}

        {/* Modal Exportar Gabarito */}
        <Dialog open={exportarZipModalOpen} onClose={() => setExportarZipModalOpen(false)} maxWidth="xs" fullWidth>
          <DialogTitle>Exportar Gabarito</DialogTitle>
          <DialogContent>
            <TextField
              label="Senha do Evento"
              type="password"
              value={senhaZip}
              onChange={e => setSenhaZip(e.target.value)}
              fullWidth
              autoFocus
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={handleExportarZip} variant="contained">Exportar</Button>
            <Button onClick={() => setExportarZipModalOpen(false)}>Cancelar</Button>
          </DialogActions>
        </Dialog>
        <Snackbar open={exportSnackbar.open} autoHideDuration={4000} onClose={() => setExportSnackbar({ ...exportSnackbar, open: false })}>
          <Alert severity={exportSnackbar.severity}>{exportSnackbar.message}</Alert>
        </Snackbar>

        <Snackbar open={snackbar.open} autoHideDuration={3500} onClose={() => setSnackbar({ ...snackbar, open: false })}>
          <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
        </Snackbar>
      </Paper>
    </Layout>
  );
};

export default GabaritoPage;