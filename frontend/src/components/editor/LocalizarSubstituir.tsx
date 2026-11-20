import React, { useEffect, useMemo, useState } from 'react';
import { Editor } from '@tiptap/react';
import { Box, Button, Checkbox, FormControlLabel, IconButton, TextField, Tooltip, Typography } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';

type Trecho = { from: number; to: number };

function encontrar(editor: Editor, termo: string, diferenciar: boolean): Trecho[] {
  const achados: Trecho[] = [];
  if (!termo) return achados;
  const alvo = diferenciar ? termo : termo.toLocaleLowerCase('pt-BR');
  editor.state.doc.descendants((node, pos) => {
    if (!node.isText || !node.text) return;
    const texto = diferenciar ? node.text : node.text.toLocaleLowerCase('pt-BR');
    let i = texto.indexOf(alvo);
    while (i >= 0) {
      achados.push({ from: pos + i, to: pos + i + alvo.length });
      i = texto.indexOf(alvo, i + alvo.length);
    }
  });
  return achados;
}

export default function LocalizarSubstituir({ editor, onFechar }: { editor: Editor; onFechar: () => void }) {
  const [termo, setTermo] = useState('');
  const [troca, setTroca] = useState('');
  const [diferenciar, setDiferenciar] = useState(false);
  const [atual, setAtual] = useState(-1);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    const atualizar = () => setVersao((v) => v + 1);
    editor.on('update', atualizar);
    return () => { editor.off('update', atualizar); };
  }, [editor]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const achados = useMemo(() => encontrar(editor, termo, diferenciar), [editor, termo, diferenciar, versao]);

  const irPara = (indice: number) => {
    if (!achados.length) return;
    const i = ((indice % achados.length) + achados.length) % achados.length;
    const { from, to } = achados[i];
    editor.chain().setTextSelection({ from, to }).scrollIntoView().run();
    setAtual(i);
  };

  const proximo = () => {
    const depois = editor.state.selection.to;
    const i = achados.findIndex((t) => t.from >= depois);
    irPara(i >= 0 ? i : 0);
  };

  const substituirAtual = () => {
    const { from, to } = editor.state.selection;
    const selecionado = achados.find((t) => t.from === from && t.to === to);
    if (!selecionado) {
      proximo();
      return;
    }
    editor.chain().focus().command(({ tr }) => { tr.insertText(troca, from, to); return true; }).run();
    setTimeout(proximo, 0);
  };

  const substituirTudo = () => {
    if (!achados.length) return;
    editor.chain().focus().command(({ tr }) => {
      [...achados].reverse().forEach(({ from, to }) => tr.insertText(troca, from, to));
      return true;
    }).run();
    setAtual(-1);
  };

  return (
    <Box
      role="search"
      aria-label="Localizar e substituir"
      sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, p: 1, mb: 1, borderRadius: 2,
        bgcolor: 'rgba(15, 23, 42, 0.92)', border: '1px solid rgba(56, 189, 248, 0.35)' }}
      onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); onFechar(); } }}
    >
      <TextField size="small" autoFocus label="Localizar" value={termo} onChange={(e) => { setTermo(e.target.value); setAtual(-1); }}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.shiftKey ? irPara(atual - 1) : proximo(); } }}
        sx={{ width: 200 }} />
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 70 }}>
        {termo ? `${atual >= 0 ? atual + 1 : 0} de ${achados.length}` : ''}
      </Typography>
      <Tooltip title="Anterior (Shift+Enter)"><span><IconButton size="small" aria-label="Anterior" disabled={!achados.length} onClick={() => irPara(atual - 1)}><KeyboardArrowUpIcon /></IconButton></span></Tooltip>
      <Tooltip title="Próximo (Enter)"><span><IconButton size="small" aria-label="Próximo" disabled={!achados.length} onClick={proximo}><KeyboardArrowDownIcon /></IconButton></span></Tooltip>
      <TextField size="small" label="Substituir por" value={troca} onChange={(e) => setTroca(e.target.value)} sx={{ width: 200 }} />
      <Button size="small" variant="outlined" disabled={!achados.length} onClick={substituirAtual}>Substituir</Button>
      <Button size="small" variant="outlined" disabled={!achados.length} onClick={substituirTudo}>Substituir tudo</Button>
      <FormControlLabel control={<Checkbox size="small" checked={diferenciar} onChange={(e) => setDiferenciar(e.target.checked)} />}
        label={<Typography variant="body2">Maiúsc./minúsc.</Typography>} />
      <IconButton size="small" aria-label="Fechar busca" onClick={onFechar} sx={{ ml: 'auto' }}><CloseIcon fontSize="small" /></IconButton>
    </Box>
  );
}
