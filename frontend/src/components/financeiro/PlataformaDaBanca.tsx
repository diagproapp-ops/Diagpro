import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, Divider, IconButton, Paper, Stack, Typography,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import api from '../../api';
import { DialogoAceite, DialogoTexto, Indicador, StatusChip, baixar, dataBR, dataHoraBR, erroApi, moeda } from './comum';

// A banca e a plataforma: plano, propostas e documentos para aceitar, faturas (com envio do comprovante).
const PlataformaDaBanca: React.FC = () => {
  const [d, setD] = useState<any>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [aceitar, setAceitar] = useState<{ tipo: 'proposta' | 'termo'; item: any } | null>(null);
  const [recusar, setRecusar] = useState<{ tipo: 'proposta' | 'termo'; item: any } | null>(null);

  const carregar = useCallback(() => {
    api.get('/financeiro/plataforma').then(({ data }) => setD(data)).catch((e) => setErro(erroApi(e, 'Não foi possível carregar.')));
  }, []);
  useEffect(() => { carregar(); }, [carregar]);
  const comprovante = (f: any) => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.pdf,.png,.jpg,.jpeg';
    input.onchange = async () => {
      const arq = input.files?.[0];
      if (!arq) return;
      const fd = new FormData(); fd.append('arquivo', arq);
      try { await api.post(`/financeiro/plataforma/faturas/${f.id}/comprovante`, fd); setMsg('Comprovante enviado: a plataforma vai conferir.'); carregar(); }
      catch (e: any) { setErro(erroApi(e, 'Não foi possível enviar.')); }
    };
    input.click();
  };

  if (!d) return erro ? <Alert severity="error">{erro}</Alert> : <Typography>Carregando...</Typography>;
  const abertas = d.faturas.filter((f: any) => ['aberta', 'atrasada', 'em_analise'].includes(f.status));
  return (
    <Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, minmax(0,1fr))' }, gap: 1.5, mb: 2.5 }}>
        <Indicador rotulo="Plano contratado" valor={d.plano.plano || 'Nenhum'} detalhe={d.plano.vence_em ? `válido até ${dataBR(d.plano.vence_em)}` : undefined} />
        <Indicador rotulo="Faturas em aberto" valor={moeda(abertas.reduce((s: number, f: any) => s + f.valor, 0))}
          cor={abertas.some((f: any) => f.status === 'atrasada') ? '#ef4444' : undefined} detalhe={`${abertas.length} fatura(s)`} />
        <Indicador rotulo="Pendências" valor={d.propostas.filter((p: any) => p.status === 'enviada').length + d.termos.filter((t: any) => t.status === 'pendente').length}
          detalhe="propostas e documentos para responder" />
      </Box>
      {erro && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErro(null)}>{erro}</Alert>}
      {msg && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMsg(null)}>{msg}</Alert>}

      <Secao titulo="Propostas">
        {d.propostas.length === 0 ? <Vazio /> : d.propostas.map((p: any) => (
          <Linha key={p.id}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography fontWeight={700}>{p.plano} · {p.periodicidade} · {moeda(p.valor_final)}
                {p.desconto ? <Typography component="span" variant="caption" color="text.secondary"> ({p.desconto}% de desconto sobre {moeda(p.valor)})</Typography> : null}</Typography>
              <Typography variant="caption" color="text.secondary">Proposta {p.numero} v{p.versao} · {p.validade ? `válida até ${dataBR(p.validade)}` : 'sem prazo'}
                {p.aceite ? ` · aceita por ${p.aceite.por} em ${dataHoraBR(p.aceite.em)}` : ''}</Typography>
              {p.condicoes && <Typography variant="body2" sx={{ mt: 0.5 }}>{p.condicoes}</Typography>}
            </Box>
            <StatusChip status={p.expirada ? 'cancelada' : p.status} />
            <IconButton size="small" onClick={() => baixar(`/financeiro/plataforma/arquivo/proposta/${p.id}`, `proposta-${p.numero}.pdf`)}><DownloadIcon fontSize="small" /></IconButton>
            {p.status === 'enviada' && !p.expirada && (
              <>
                <Button size="small" variant="contained" color="success" onClick={() => setAceitar({ tipo: 'proposta', item: p })}>Aceitar</Button>
                <Button size="small" color="error" onClick={() => setRecusar({ tipo: 'proposta', item: p })}>Recusar</Button>
              </>
            )}
          </Linha>
        ))}
      </Secao>

      <Secao titulo="Contratos e termos">
        {d.termos.length === 0 ? <Vazio /> : d.termos.map((t: any) => (
          <Linha key={t.id}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography fontWeight={700}>{t.titulo}</Typography>
              <Typography variant="caption" color="text.secondary">{t.descricao}{t.aceite ? ` · aceito por ${t.aceite.por} em ${dataHoraBR(t.aceite.em)}` : ''}</Typography>
            </Box>
            <StatusChip status={t.status} />
            <IconButton size="small" onClick={() => baixar(`/financeiro/plataforma/arquivo/termo/${t.id}`, `${t.titulo}.pdf`)}><DownloadIcon fontSize="small" /></IconButton>
            {t.status === 'pendente' && (
              <>
                <Button size="small" variant="contained" color="success" onClick={() => setAceitar({ tipo: 'termo', item: t })}>Aceitar</Button>
                <Button size="small" color="error" onClick={() => setRecusar({ tipo: 'termo', item: t })}>Recusar</Button>
              </>
            )}
          </Linha>
        ))}
      </Secao>

      <Secao titulo="Faturas">
        {d.faturas.length === 0 ? <Vazio /> : d.faturas.map((f: any) => (
          <Linha key={f.id}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography fontWeight={700}>{f.numero} · {moeda(f.valor)}</Typography>
              <Typography variant="caption" color="text.secondary">{f.descricao} · vence {dataBR(f.vencimento)}{f.paga_em ? ` · paga em ${dataBR(f.paga_em)}` : ''}</Typography>
              {f.motivo_devolucao && f.status !== 'paga' && <Typography variant="caption" color="error" display="block">Comprovante devolvido: {f.motivo_devolucao}</Typography>}
            </Box>
            <StatusChip status={f.status} />
            {['aberta', 'atrasada'].includes(f.status) && <Button size="small" startIcon={<UploadFileIcon />} onClick={() => comprovante(f)}>Enviar comprovante</Button>}
          </Linha>
        ))}
      </Secao>

      {d.documentos.length > 0 && (
        <Secao titulo="Documentos">
          {d.documentos.map((x: any) => (
            <Linha key={x.id}>
              <Chip size="small" label={x.tipo === 'comprovante' ? 'Comprovante' : 'Documento'} />
              <Typography variant="body2" sx={{ flex: 1 }}>{x.nome}{x.descricao ? ` — ${x.descricao}` : ''}</Typography>
              <Typography variant="caption" color="text.secondary">{dataHoraBR(x.enviado_em)}</Typography>
              <IconButton size="small" onClick={() => baixar(`/financeiro/plataforma/arquivo/documento/${x.id}`, x.nome)}><DownloadIcon fontSize="small" /></IconButton>
            </Linha>
          ))}
        </Secao>
      )}

      <DialogoAceite aberto={!!aceitar} titulo={aceitar?.tipo === 'proposta' ? 'Aceitar a proposta' : 'Aceitar o documento'} onFechar={() => setAceitar(null)}
        texto={<Typography variant="body2">Baixe e leia o PDF antes de aceitar. {aceitar?.tipo === 'proposta' ? 'O plano da banca passa a ser o desta proposta.' : ''}</Typography>}
        onConfirmar={async (senha) => {
          const a = aceitar!;
          await api.post(`/financeiro/plataforma/${a.tipo === 'proposta' ? 'propostas' : 'termos'}/${a.item.id}/aceitar`, { senha });
          setAceitar(null); setMsg('Aceite registrado.'); carregar();
        }} />
      <DialogoTexto aberto={!!recusar} titulo="Recusar" rotulo="Motivo (a plataforma vê)" botao="Recusar" cor="error" onFechar={() => setRecusar(null)}
        onConfirmar={async (m) => {
          const r = recusar!;
          await api.post(`/financeiro/plataforma/${r.tipo === 'proposta' ? 'propostas' : 'termos'}/${r.item.id}/recusar`, { motivo: m });
          setRecusar(null); carregar();
        }} />
    </Box>
  );
};

const Secao: React.FC<{ titulo: string; children: React.ReactNode }> = ({ titulo, children }) => (
  <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 2 }}>
    <Typography fontWeight={800} sx={{ mb: 1 }}>{titulo}</Typography>
    <Stack divider={<Divider />}>{children}</Stack>
  </Paper>
);
const Linha: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 1, flexWrap: { xs: 'wrap', md: 'nowrap' } }}>{children}</Stack>
);
const Vazio = () => <Typography variant="body2" color="text.secondary">Nada por aqui.</Typography>;

export default PlataformaDaBanca;
