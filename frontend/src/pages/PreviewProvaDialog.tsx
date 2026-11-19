import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  List,
  ListItem,
  ListItemText,
  Typography,
  Divider,
  Box,
  Chip,
  Stack,
  Alert,
  Tooltip,
  Button,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TableHead,
} from '@mui/material';
import WarningIcon from '@mui/icons-material/Warning';
import DoneIcon from '@mui/icons-material/Done';

type QuestaoResumo = {
  codigo_curto_questao: string;
  enunciado?: string;
  tipo?: string;
  anulada?: boolean;
  revisada?: boolean;
};

type BlocoQuestao = {
  nome_disciplina: string;
  qtd_questoes: number;
  peso: number;
  ordem: number;
  conhecimento_basico: boolean;
  observacoes?: string;
  tipo_questao?: string;
  conteudos?: string[];
  questoes?: QuestaoResumo[];
  minimo_aprovacao?: string;
};

type Discursiva = {
  tema?: string;
  peso?: number;
  minimo_linhas?: number;
  criterios?: string;
};

type PreviewProvaDialogProps = {
  open: boolean;
  onClose: () => void;
  prova: {
    nome_prova_montada: string;
    titulo_prova?: string;
    nome_cargo?: string;
    status_montagem?: string;
    responsavel_montagem?: string;
    data_modificacao?: string;
    data_criacao?: string;
    blocos_questoes: BlocoQuestao[];
    tem_discursiva?: boolean;
    discursiva?: Discursiva;
    total_questoes?: number;
    duracao?: string;
    pontos_totais?: number;
  } | null;
  onFinalizar?: () => void;
  onExportar?: () => void;
};

function getResumoValidacao(prova: any) {
  const avisos: string[] = [];
  if (!prova.blocos_questoes.length) avisos.push("Nenhum bloco/disciplina adicionado.");
  prova.blocos_questoes.forEach((bloco: BlocoQuestao, idx: number) => {
    if (!bloco.qtd_questoes) avisos.push(`O bloco "${bloco.nome_disciplina}" não possui questões.`);
    if (!bloco.conteudos?.length) avisos.push(`O bloco "${bloco.nome_disciplina}" não possui conteúdos associados.`);
    if (bloco.qtd_questoes && bloco.questoes && bloco.questoes.length !== bloco.qtd_questoes) avisos.push(`Quantidade de questões sorteadas diferente do esperado no bloco "${bloco.nome_disciplina}".`);
  });
  return avisos;
}

const PreviewProvaDialog: React.FC<PreviewProvaDialogProps> = ({
  open, onClose, prova, onFinalizar, onExportar
}) => {
  if (!prova) return null;
  const totalQuestoes = prova.total_questoes
    ?? prova.blocos_questoes.reduce((acc, b) => acc + (b.qtd_questoes ?? 0), 0)
    + (prova.tem_discursiva ? 1 : 0);

  const avisos = getResumoValidacao(prova);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Prévia Estrutural da Prova
        <Chip
          label={prova.status_montagem || "Indefinido"}
          color={prova.status_montagem === "Concluída" ? "success" : "warning"}
          size="small"
          sx={{ ml: 2 }}
        />
      </DialogTitle>
      <DialogContent>
        {/* Resumo geral */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="h6">{prova.titulo_prova || prova.nome_prova_montada}</Typography>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 1 }}>
            {prova.nome_cargo && (
              <Typography variant="subtitle1" component="span"><b>Cargo:</b> {prova.nome_cargo}</Typography>
            )}
            {prova.duracao && (
              <Typography variant="subtitle2" component="span"><b>Duração:</b> {prova.duracao}</Typography>
            )}
            <Typography variant="subtitle2" component="span"><b>Total de questões:</b> {totalQuestoes}</Typography>
            {prova.pontos_totais !== undefined && (
              <Typography variant="subtitle2" component="span"><b>Pontos totais:</b> {prova.pontos_totais}</Typography>
            )}
            {prova.tem_discursiva && (
              <Chip label="Inclui Discursiva" color="secondary" size="small"/>
            )}
          </Stack>
          <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
            {prova.responsavel_montagem && (
              <Typography variant="body2" component="span">Responsável: {prova.responsavel_montagem}</Typography>
            )}
            {prova.data_modificacao && (
              <Typography variant="body2" component="span">Última edição: {prova.data_modificacao}</Typography>
            )}
          </Stack>
        </Box>

        {/* Validações/avisos */}
        {avisos.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Alert severity="warning" icon={<WarningIcon/>}>
              {avisos.map((a, i) => <div key={i}>{a}</div>)}
            </Alert>
          </Box>
        )}

        <Divider sx={{ mb: 2 }} />
        <Typography variant="subtitle1" fontWeight="bold" sx={{ mb: 1 }}>Blocos/Disciplinas:</Typography>
        <List>
          {prova.blocos_questoes
            .sort((a, b) => (a.ordem || 0) - (b.ordem || 0))
            .map((bloco, idx) => (
              <Box key={idx} sx={{ mb: 2, borderRadius: 2, bgcolor: "rgba(15, 23, 42, 0.7)", px: 1 }}>
                <ListItem alignItems="flex-start" disableGutters>
                  <ListItemText
                    primary={
                      <span>
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <Typography fontWeight="bold" color="primary" component="span">
                            {bloco.ordem}. {bloco.nome_disciplina}
                          </Typography>
                          <Chip
                            label={bloco.conhecimento_basico ? "BÁSICO" : "ESPECÍFICO"}
                            color={bloco.conhecimento_basico ? "info" : "success"}
                            size="small"
                          />
                          {bloco.tipo_questao && (
                            <Chip label={bloco.tipo_questao} color="default" size="small"/>
                          )}
                          {bloco.minimo_aprovacao && (
                            <Tooltip title="Mínimo para aprovação">
                              <Chip label={bloco.minimo_aprovacao} color="warning" size="small"/>
                            </Tooltip>
                          )}
                        </Stack>
                      </span>
                    }
                    secondary={
                      <span>
                        <Stack spacing={0.5}>
                          <Typography variant="body2" color="textSecondary" component="span">
                            Questões: <b>{bloco.qtd_questoes}</b>
                            {"  |  "}Peso: <b>{bloco.peso}</b>
                          </Typography>
                          {bloco.observacoes && (
                            <Typography variant="caption" color="textSecondary" component="span">
                              Obs: {bloco.observacoes}
                            </Typography>
                          )}
                          {bloco.conteudos && bloco.conteudos.length > 0 && (
                            <Typography variant="caption" color="textSecondary" component="span">
                              Conteúdos: {bloco.conteudos.join(", ")}
                            </Typography>
                          )}
                        </Stack>
                      </span>
                    }
                  />
                </ListItem>
                {/* Questões sorteadas */}
                {bloco.questoes && bloco.questoes.length > 0 && (
                  <Table size="small" sx={{ mb: 1, bgcolor: "background.default" }}>
                    <TableHead>
                      <TableRow>
                        <TableCell>Código</TableCell>
                        <TableCell>Enunciado</TableCell>
                        <TableCell>Tipo</TableCell>
                        <TableCell>Anulada?</TableCell>
                        <TableCell>Revisada?</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {bloco.questoes.map((q, i) => (
                        <TableRow key={i}>
                          <TableCell>{q.codigo_curto_questao}</TableCell>
                          <TableCell>
                            <Tooltip title={q.enunciado ?? ""} placement="top">
                              <span>{q.enunciado?.slice(0, 60) ?? "-"}</span>
                            </Tooltip>
                          </TableCell>
                          <TableCell>{q.tipo ?? "-"}</TableCell>
                          <TableCell>
                            {q.anulada ? <WarningIcon fontSize="small" color="error"/> : <DoneIcon fontSize="small" color="success"/>}
                          </TableCell>
                          <TableCell>
                            {q.revisada ? <DoneIcon fontSize="small" color="success"/> : "-"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </Box>
          ))}
        </List>

        {/* Discursiva */}
        {prova.tem_discursiva && prova.discursiva && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle1" fontWeight="bold">Discursiva</Typography>
            <Stack spacing={1} sx={{ mb: 2 }}>
              {prova.discursiva.tema && (
                <Typography variant="body2" component="span"><b>Tema:</b> {prova.discursiva.tema}</Typography>
              )}
              {prova.discursiva.peso && (
                <Typography variant="body2" component="span"><b>Peso:</b> {prova.discursiva.peso}</Typography>
              )}
              {prova.discursiva.minimo_linhas && (
                <Typography variant="body2" component="span"><b>Mínimo de linhas:</b> {prova.discursiva.minimo_linhas}</Typography>
              )}
              {prova.discursiva.criterios && (
                <Typography variant="body2" component="span"><b>Critérios:</b> {prova.discursiva.criterios}</Typography>
              )}
            </Stack>
          </>
        )}

        {/* Botões de ação */}
        <Stack direction="row" spacing={2} sx={{ mt: 2, mb: 1 }}>
          {onFinalizar && (
            <Button variant="contained" color="success" onClick={onFinalizar}>
              Finalizar Montagem
            </Button>
          )}
          {onExportar && (
            <Button variant="outlined" color="primary" onClick={onExportar}>
              Exportar Prévia
            </Button>
          )}
          <Button variant="text" color="inherit" onClick={onClose}>Fechar</Button>
        </Stack>
      </DialogContent>
    </Dialog>
  );
};

export default PreviewProvaDialog;