import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, FormControlLabel, Switch, Table, TableBody, TableCell, TableHead,
  TableRow, TextField, Typography,
} from '@mui/material';
import api from '../../api';
import { Aviso, BarraSalvar, Secao, mensagemErro } from './configComum';

type Item = { item: string; estado: 'ok' | 'aviso' | 'erro'; detalhe: string };
type Saude = { geral: string; conferido_em: string; itens: Item[] };
type Backup = { arquivo: string; criado_em: string; motivo: string; tamanho: number };
type Cfg = { backup: { automatico: boolean; hora: number; manter: number }; manutencao: { ativa: boolean; mensagem: string } };

const COR: Record<string, 'success' | 'warning' | 'error'> = { ok: 'success', aviso: 'warning', erro: 'error' };
const ROTULO: Record<string, string> = { ok: 'OK', aviso: 'Atenção', erro: 'Problema' };
const MOTIVO: Record<string, string> = { automatico: 'Automático', manual: 'Manual' };
const tam = (n: number) => (n > 1024 ** 2 ? `${(n / 1024 ** 2).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
const dataHora = (iso: string) => new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });

// Saúde do sistema, backups e modo manutenção (admin geral)
const PlataformaSaudeTab: React.FC = () => {
  const [saude, setSaude] = useState<Saude | null>(null);
  const [lista, setLista] = useState<Backup[] | null>(null);
  const [pastaBk, setPastaBk] = useState('');
  const [original, setOriginal] = useState<Cfg | null>(null);
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [fazendo, setFazendo] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<{ texto: string; tipo: 'success' | 'error' } | null>(null);

  const carregar = useCallback(async () => {
    setSaude(null);
    const [s, b, p] = await Promise.allSettled([api.get('/admin/sistema/saude'), api.get('/admin/sistema/backups'), api.get('/config/plataforma')]);
    if (s.status === 'fulfilled') setSaude(s.value.data);
    if (b.status === 'fulfilled') { setLista(b.value.data.itens); setPastaBk(b.value.data.pasta); }
    if (p.status === 'fulfilled') {
      const c = { backup: p.value.data.backup, manutencao: p.value.data.manutencao };
      setOriginal(c); setCfg(c);
    }
  }, []);
  useEffect(() => { carregar(); }, [carregar]);

  const backupAgora = async () => {
    setFazendo(true);
    try {
      const { data } = await api.post('/admin/sistema/backups');
      setMsg({ texto: `Backup feito e conferido: ${data.arquivo} (${tam(data.tamanho_cifrado)}).`, tipo: 'success' });
      carregar();
    } catch (e: any) {
      setMsg({ texto: mensagemErro(e, 'O backup falhou.'), tipo: 'error' });
    } finally {
      setFazendo(false);
    }
  };

  const salvar = async () => {
    if (!cfg) return;
    if (cfg.manutencao.ativa && !original?.manutencao.ativa &&
      !window.confirm('Ligar o modo manutenção?\n\nTodos, menos o administrador geral, deixam de conseguir usar o sistema até você desligar.')) return;
    setSalvando(true);
    try {
      const { data } = await api.put('/config/plataforma', cfg);
      const c = { backup: data.backup, manutencao: data.manutencao };
      setOriginal(c); setCfg(c);
      setMsg({ texto: 'Configurações salvas.', tipo: 'success' });
      carregar();
    } catch (e: any) {
      setMsg({ texto: mensagemErro(e), tipo: 'error' });
    } finally {
      setSalvando(false);
    }
  };

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="h6" fontWeight={700}>Saúde e backups</Typography>
        <Button onClick={carregar}>Conferir de novo</Button>
      </Box>

      <Secao titulo="Saúde do sistema" descricao="Conferências do que mantém o DiagPro seguro e no ar.">
        {!saude ? <CircularProgress /> : (
          <>
            <Alert severity={COR[saude.geral] || 'info'} sx={{ mb: 1.5 }}>
              {saude.geral === 'ok' ? 'Tudo certo.' : saude.geral === 'aviso' ? 'Funcionando, com pontos de atenção.' : 'Há problemas que precisam de ação.'}
              {' '}Conferido em {dataHora(saude.conferido_em)}.
            </Alert>
            <Table size="small">
              <TableBody>
                {saude.itens.map(i => (
                  <TableRow key={i.item}>
                    <TableCell sx={{ width: 110 }}><Chip size="small" color={COR[i.estado]} label={ROTULO[i.estado]} /></TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{i.item}</TableCell>
                    <TableCell>{i.detalhe}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </>
        )}
      </Secao>

      <Secao titulo="Backups do banco" descricao={`Cifrados e conferidos logo depois de gerados. Ficam só neste servidor${pastaBk ? ` (${pastaBk})` : ''}; não há download pela web.`}>
        {cfg && (
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
            <FormControlLabel label="Backup automático diário"
              control={<Switch checked={cfg.backup.automatico} onChange={e => setCfg({ ...cfg, backup: { ...cfg.backup, automatico: e.target.checked } })} />} />
            <TextField size="small" type="number" label="Hora (0-23)" sx={{ width: 120 }} value={cfg.backup.hora} inputProps={{ min: 0, max: 23 }}
              onChange={e => setCfg({ ...cfg, backup: { ...cfg.backup, hora: Number(e.target.value) } })} />
            <TextField size="small" type="number" label="Guardar (automáticos)" sx={{ width: 180 }} value={cfg.backup.manter} inputProps={{ min: 3, max: 365 }}
              onChange={e => setCfg({ ...cfg, backup: { ...cfg.backup, manter: Number(e.target.value) } })} />
            <Box sx={{ flexGrow: 1 }} />
            <Button variant="contained" onClick={backupAgora} disabled={fazendo}>{fazendo ? 'Fazendo backup...' : 'Fazer backup agora'}</Button>
          </Box>
        )}
        {!lista ? <CircularProgress /> : !lista.length ? <Typography color="text.secondary">Nenhum backup ainda.</Typography> : (
          <Box sx={{ maxHeight: 280, overflowY: 'auto' }}>
            <Table size="small">
              <TableHead><TableRow><TableCell>Quando</TableCell><TableCell>Tipo</TableCell><TableCell>Tamanho</TableCell><TableCell>Arquivo</TableCell></TableRow></TableHead>
              <TableBody>
                {lista.map(b => (
                  <TableRow key={b.arquivo}>
                    <TableCell>{dataHora(b.criado_em)}</TableCell>
                    <TableCell>{MOTIVO[b.motivo] || `Antes de ${b.motivo.replace(/^pre-/, '').replace(/-/g, ' ')}`}</TableCell>
                    <TableCell>{tam(b.tamanho)}</TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 12 }}>{b.arquivo}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          Para restaurar, siga o procedimento do README (seção Backup e restauração). Guarde uma cópia offline da chave dos backups.
        </Typography>
      </Secao>

      {cfg && (
        <Secao titulo="Modo manutenção" descricao="Bloqueia o uso para todos, menos o administrador geral (ex.: durante uma atualização). A mensagem aparece em todas as telas.">
          <FormControlLabel label={cfg.manutencao.ativa ? 'Manutenção LIGADA' : 'Manutenção desligada'}
            control={<Switch color="warning" checked={cfg.manutencao.ativa} onChange={e => setCfg({ ...cfg, manutencao: { ...cfg.manutencao, ativa: e.target.checked } })} />} />
          <TextField fullWidth sx={{ mt: 1.5 }} label="Mensagem para os usuários" value={cfg.manutencao.mensagem} inputProps={{ maxLength: 300 }}
            onChange={e => setCfg({ ...cfg, manutencao: { ...cfg.manutencao, mensagem: e.target.value } })} />
        </Secao>
      )}

      <BarraSalvar salvando={salvando} onSalvar={salvar} alterado={JSON.stringify(cfg) !== JSON.stringify(original)} />
      <Aviso msg={msg} onFechar={() => setMsg(null)} />
    </>
  );
};

export default PlataformaSaudeTab;
