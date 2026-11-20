import React, { useEffect, useState } from 'react';
import { Alert, Checkbox, FormControlLabel, FormGroup, Paper, Typography } from '@mui/material';
import api from '../api';

type Tipo = { tipo: string; rotulo: string; obrigatorio: boolean; email: boolean };

// Minha conta: quais avisos a pessoa quer também por e-mail (os de segurança são sempre enviados)
const PreferenciasAvisos: React.FC<{ sx?: object }> = ({ sx }) => {
  const [tipos, setTipos] = useState<Tipo[] | null>(null);
  const [emailLigado, setEmailLigado] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.get('/notificacoes/preferencias')
      .then(({ data }) => { setTipos(data.tipos); setEmailLigado(data.email_da_plataforma_ligado); })
      .catch(() => setErro('Não foi possível carregar as preferências.'));
  }, []);

  const alterar = async (t: Tipo, valor: boolean) => {
    setTipos(ts => ts && ts.map(x => (x.tipo === t.tipo ? { ...x, email: valor } : x)));
    try {
      const { data } = await api.put('/notificacoes/preferencias', { email: { [t.tipo]: valor } });
      setTipos(data.tipos);
    } catch {
      setErro('Não foi possível salvar.');
      setTipos(ts => ts && ts.map(x => (x.tipo === t.tipo ? { ...x, email: !valor } : x)));
    }
  };

  return (
    <Paper variant="outlined" sx={sx}>
      <Typography variant="subtitle1" fontWeight={700}>Avisos por e-mail</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Todos os avisos aparecem no sino do topo da tela. Escolha quais também chegam no seu e-mail.
        Por segurança, os e-mails nunca trazem conteúdo de prova, só o aviso e o link.
      </Typography>
      {!emailLigado && <Alert severity="info" sx={{ mb: 1.5 }}>O envio de e-mails ainda não foi ligado pela plataforma.</Alert>}
      {erro && <Alert severity="error" sx={{ mb: 1.5 }}>{erro}</Alert>}
      {tipos && (
        <FormGroup>
          {tipos.map(t => (
            <FormControlLabel key={t.tipo}
              control={<Checkbox checked={t.email} disabled={t.obrigatorio} onChange={e => alterar(t, e.target.checked)} />}
              label={t.obrigatorio ? `${t.rotulo} (segurança: sempre enviado)` : t.rotulo} />
          ))}
        </FormGroup>
      )}
    </Paper>
  );
};

export default PreferenciasAvisos;
