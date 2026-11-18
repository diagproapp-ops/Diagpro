import React, { useEffect, useState, useMemo } from 'react';
import {
  Box, Typography, Paper, LinearProgress, Select, MenuItem, FormControl,
  InputLabel, Chip, List, ListItem, ListItemText, Divider, Button, Stack,
  CircularProgress, Snackbar, Alert, TextField
} from '@mui/material';
import { DndContext, useDraggable, useDroppable, closestCenter, DragEndEvent } from '@dnd-kit/core';
import Layout from '../components/Layout';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { v4 as uuidv4 } from 'uuid'; // Importa uuid para gerar id_bloco

type DisciplinaProva = {
  qtd_questoes?: number;
  nome_disciplina_na_prova?: string;
  peso_por_questao?: number;
  ordem_na_prova?: number;
  observacoes?: string;
};

type Cargo = {
  id_cargo: string;
  nome_cargo: string;
  codigo_cargo?: string;
  nivel: string;
  turno: string;
  tem_discursiva?: boolean;
  disciplinas_prova?: DisciplinaProva[];
};

type Conteudo = {
  id_conteudo: string;
  nome_conteudo: string;
  nivel?: string;
  turno?: string;
  quantidade?: number;
  respondidas?: number;
};

function DraggableItem({ id, children }: { id: string; children: React.ReactNode }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id });
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      style={{
        opacity: isDragging ? 0.5 : 1,
        cursor: 'grab',
        marginBottom: 10,
        boxShadow: isDragging
          ? '0 2px 16px 2px rgba(33,150,243,0.16)'
          : '0 1px 4px 0 rgba(0,0,0,0.10)',
        transition: 'box-shadow 0.3s',
      }}
    >
      {children}
    </div>
  );
}

function DroppableArea({ id, children, style }: { id: string; children: React.ReactNode; style?: React.CSSProperties }) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      style={{
        minHeight: 350,
        padding: 20,
        border: `2px dashed ${isOver ? '#1976d2' : '#e0e0e0'}`,
        background: isOver ? '#e3f2fd' : '#fafafa',
        borderRadius: 14,
        transition: 'background 0.3s, border 0.3s',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

const MontagemProvaPage: React.FC = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();

  const [cargos, setCargos] = useState<Cargo[]>([]);
  const [conteudos, setConteudos] = useState<Conteudo[]>([]);
  const [carregandoCargos, setCarregandoCargos] = useState(true);
  const [carregandoConteudos, setCarregandoConteudos] = useState(false);

  const [cargo, setCargo] = useState('');
  const [nivel, setNivel] = useState('');
  const [turno, setTurno] = useState('');
  const [montagem, setMontagem] = useState<Conteudo[]>([]);
  const [snackbar, setSnackbar] = useState<{ open: boolean, message: string, severity: "success" | "error" | "info" }>({ open: false, message: '', severity: "success" });
  const [filtroNomeConteudo, setFiltroNomeConteudo] = useState('');

  // Busca cargos
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

  // Busca conteúdos do evento
  useEffect(() => {
    async function fetchConteudos() {
      setCarregandoConteudos(true);
      try {
        const res = await api.get(`/conteudos/eventos/${eventId}/conteudos`);
        setConteudos(res.data);
      } catch {
        setSnackbar({ open: true, message: "Erro ao carregar conteúdos", severity: "error" });
      }
      setCarregandoConteudos(false);
    }
    fetchConteudos();
  }, [eventId]);

  const niveis = useMemo(() => (
    [...new Set(conteudos.map(c => c.nivel).filter(Boolean))] as string[]
  ), [conteudos]);
  const turnos = useMemo(() => (
    [...new Set(conteudos.map(c => c.turno).filter(Boolean))] as string[]
  ), [conteudos]);

  const conteudosFiltrados = useMemo(() => {
    return conteudos.filter(c =>
      (nivel ? c.nivel === nivel : true) &&
      (turno ? c.turno === turno : true) &&
      (filtroNomeConteudo.trim() === '' ||
        c.nome_conteudo.toLowerCase().includes(filtroNomeConteudo.trim().toLowerCase()))
    );
  }, [conteudos, nivel, turno, filtroNomeConteudo]);

  const cargoSelecionado = useMemo(
    () => cargos.find(c => c.id_cargo === cargo),
    [cargos, cargo]
  );

  const totalQuestoes = useMemo(() => {
    if (!cargoSelecionado) return 0;
    let soma = (cargoSelecionado.disciplinas_prova || []).reduce(
      (acc, disc) => acc + (disc.qtd_questoes || 0), 0
    );
    if (cargoSelecionado.tem_discursiva) soma += 1;
    return soma;
  }, [cargoSelecionado]);

  const questoesSelecionadas = montagem.reduce((acc, item) => acc + (item.quantidade || 0), 0);

  const progresso = useMemo(() => {
    if (!totalQuestoes) return 0;
    return Math.min(100, (questoesSelecionadas / totalQuestoes) * 100);
  }, [totalQuestoes, questoesSelecionadas]);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    if (
      over.id === 'montagem-droppable' &&
      !montagem.find(item => item.id_conteudo === active.id)
    ) {
      const conteudo = conteudosFiltrados.find(c => c.id_conteudo === active.id);
      if (conteudo) setMontagem(prev => [...prev, conteudo]);
    }
  }

  function handleRemoverConteudo(id: string) {
    setMontagem(m => m.filter(c => c.id_conteudo !== id));
  }

  async function handleFinalizarMontagem() {
    if (progresso < 100) {
      setSnackbar({ open: true, message: "Complete todos os conteúdos para finalizar a montagem da prova!", severity: "error" });
      return;
    }
    if (!cargo) {
      setSnackbar({ open: true, message: "Selecione um cargo.", severity: "error" });
      return;
    }
    try {
      const nomeCargo = cargos.find(c => c.id_cargo === cargo)?.nome_cargo || '';
      // Gera um id_bloco único para cada bloco
      const blocos_questoes = montagem.map((item, idx) => ({
        id_bloco: uuidv4(),
        nome_disciplina: item.nome_conteudo,
        qtd_questoes: item.quantidade ?? 0,
        peso: 1.0,
        ordem: idx + 1,
        conhecimento_basico: false
      }));
      await api.post(
        `/provas/eventos/${eventId}/provas-montadas/${cargo}`,
        {
          nome_prova_montada: nomeCargo,
          blocos_questoes
        }
      );
      setSnackbar({ open: true, message: "Montagem salva com sucesso!", severity: "success" });
      setTimeout(() => navigate(-1), 1200);
    } catch (e: any) {
      setSnackbar({ open: true, message: "Erro ao salvar a prova montada.", severity: "error" });
    }
  }

  return (
    <Layout>
      <Paper sx={{ p: { xs: 2, md: 4 }, borderRadius: 5, boxShadow: 3 }}>
        {/* Título e botões */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 2,
          flexWrap: 'wrap',
          gap: 2
        }}>
          <Typography variant="h5" fontWeight="bold" color="primary.dark">
            Montagem da Prova
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
              size="large"
              onClick={handleFinalizarMontagem}
              sx={{ borderRadius: 2, fontWeight: 'bold' }}
              disabled={progresso !== 100 || montagem.length === 0 || !cargo}
            >
              Finalizar Montagem
            </Button>
          </Box>
        </Box>
        <Divider sx={{ mb: 3 }} />

        {/* Filtros */}
        <Stack spacing={2} sx={{ maxWidth: 800, mb: 3 }}>
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
                  {[
                    c.codigo_cargo,
                    c.nome_cargo,
                    c.nivel,
                    c.turno
                  ].filter(Boolean).join(' - ')}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth size="small">
            <InputLabel id="nivel-label">Nível</InputLabel>
            <Select
              labelId="nivel-label"
              value={nivel}
              label="Nível"
              onChange={e => setNivel(e.target.value as string)}
            >
              <MenuItem value="">Todos</MenuItem>
              {niveis.map(n => <MenuItem key={n} value={n}>{n}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl fullWidth size="small">
            <InputLabel id="turno-label">Turno</InputLabel>
            <Select
              labelId="turno-label"
              value={turno}
              label="Turno"
              onChange={e => setTurno(e.target.value as string)}
            >
              <MenuItem value="">Todos</MenuItem>
              {turnos.map(t => <MenuItem key={t} value={t}>{t}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField
            label="Buscar conteúdo pelo nome"
            value={filtroNomeConteudo}
            onChange={e => setFiltroNomeConteudo(e.target.value)}
            size="small"
          />
        </Stack>

        {/* Barra de progresso */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            Progresso da Prova: <b>{questoesSelecionadas}/{totalQuestoes}</b> questões
          </Typography>
          <LinearProgress
            variant="determinate"
            value={progresso}
            color={progresso === 100 ? 'success' : 'primary'}
            sx={{
              height: 14,
              borderRadius: 5,
              background: '#e0e0e0'
            }}
          />
        </Box>

        {/* Áreas de montagem e conteúdos lado a lado */}
        <DndContext onDragEnd={handleDragEnd} collisionDetection={closestCenter}>
          <Box
            sx={{
              display: "flex",
              gap: 4,
              flexDirection: { xs: "column", md: "row" },
              mb: 2,
            }}
          >
            {/* Montagem da Prova */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="h6" fontWeight="bold" sx={{ mb: 3 }}>
                Conteúdos Selecionados
              </Typography>
              <DroppableArea id="montagem-droppable" style={{ minHeight: 350 }}>
                {montagem.length === 0 ? (
                  <Typography color="text.secondary" align="center">
                    Arraste conteúdos para montar a prova
                  </Typography>
                ) : (
                  <List>
                    {montagem.map(item => (
                      <ListItem
                        key={item.id_conteudo}
                        secondaryAction={
                          <Button
                            color="error"
                            size="small"
                            onClick={() => handleRemoverConteudo(item.id_conteudo)}
                          >
                            Remover
                          </Button>
                        }
                        sx={{
                          mb: 1.5,
                          borderRadius: 2,
                          bgcolor: "#e3f2fd",
                          boxShadow: 1,
                        }}
                      >
                        <Chip
                          label={item.nome_conteudo}
                          color="primary"
                          sx={{ mr: 2, fontWeight: 'bold' }}
                        />
                        <ListItemText
                          primary={`Questões: ${item.quantidade ?? 0}`}
                          secondary={item.nivel || item.turno ? `${item.nivel ?? ''}${item.nivel && item.turno ? ' • ' : ''}${item.turno ?? ''}` : undefined}
                        />
                      </ListItem>
                    ))}
                  </List>
                )}
              </DroppableArea>
            </Box>
            {/* Conteúdos do Evento */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
                Conteúdos do Evento
              </Typography>
              <DroppableArea
                id="conteudos-droppable"
                style={{ background: 'none', border: 'none', minHeight: 0, padding: 0 }}
              >
                <Box sx={{
                  maxHeight: 430,
                  overflowY: 'auto',
                  pr: 1
                }}>
                  {carregandoConteudos ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                      <CircularProgress size={32} />
                    </Box>
                  ) : conteudosFiltrados.length === 0 ? (
                    <Typography color="text.secondary" align="center">
                      Nenhum conteúdo encontrado para os filtros selecionados
                    </Typography>
                  ) : (
                    conteudosFiltrados.map(item => (
                      <DraggableItem id={item.id_conteudo} key={item.id_conteudo}>
                        <Paper
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            mb: 1.5,
                            p: 1.5,
                            cursor: "grab",
                            bgcolor: "#f5f5f5",
                            borderRadius: 2,
                            boxShadow: 1,
                            transition: "box-shadow 0.3s, border-color 0.3s",
                            border: "2px solid transparent",
                            "&:hover": {
                              boxShadow: 4,
                              borderColor: "#1976d2",
                            },
                          }}
                          elevation={0}
                        >
                          <Chip label={item.nome_conteudo} sx={{ mr: 2, fontWeight: 'bold' }} color="primary" />
                          <Typography variant="body2" sx={{ color: "#666" }}>
                            Questões disponíveis: {item.quantidade ?? 0}
                          </Typography>
                          {(item.nivel || item.turno) && (
                            <Typography variant="caption" sx={{ ml: 2, color: "#888" }}>
                              {item.nivel}{item.nivel && item.turno ? ' • ' : ''}{item.turno}
                            </Typography>
                          )}
                        </Paper>
                      </DraggableItem>
                    ))
                  )}
                </Box>
              </DroppableArea>
            </Box>
          </Box>
        </DndContext>
        <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
          <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
        </Snackbar>
      </Paper>
    </Layout>
  );
};

export default MontagemProvaPage;