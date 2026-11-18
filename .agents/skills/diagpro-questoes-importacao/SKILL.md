---
name: diagpro-questoes-importacao
description: Trabalha no banco de questões do DiagPro, tipos de questão, alternativas, itens certo/errado, questões discursivas, textos de referência, importação DOCX, revisão, histórico e códigos curtos.
---

# Banco de questões e importação DOCX

## Tipos descritos
- `MULTIPLA_ESCOLHA`
- `CERTO_ERRADO`
- `DISCURSIVA`
- `SUBJETIVA`

O relatório cita `QuestoesBanco`, `OpcoesQuestao`, `ItensVerdadeiroFalso`, `DetalhesQuestaoDiscursiva`, `HistoricoRevisaoQuestao` e `TextosReferenciaGeral`. Confirme campos, constraints e enums reais.

## Integridade do domínio
- Preserve enunciado, formatação rica, imagens, alternativas, gabaritos preliminar/definitivo e metadados.
- Uma questão de múltipla escolha deve respeitar quantidade/formato de alternativas e regra de resposta correta definida pelo domínio.
- Itens certo/errado precisam manter ordenação e vínculo com a questão.
- Questões discursivas/subjetivas devem preservar resposta esperada, palavras-chave, linhas e nota máxima quando aplicável.
- Textos de referência compartilhados precisam manter vínculos consistentes nos dois sentidos; o relatório cita `sincronizar_vinculo_texto_questao()`.
- Códigos curtos são únicos no escopo previsto (por tenant/tipo, conforme relatório); trate concorrência com constraint/transaction, não só checagem prévia.
- Revisões devem gerar histórico imutável suficiente para reconstruir quem fez o quê e quando.

## Importação DOCX
1. Inspecione `importador.py`, `docx_parser.py`, `routes/questoes.py` e fixtures reais.
2. Preserve a etapa de pré-visualização e confirmação citada no relatório.
3. Não grave importação parcial sem uma transação ou mecanismo explícito de staging.
4. Trate DOCX como arquivo não confiável: limite tamanho, valide formato, evite extração insegura e rejeite estruturas inválidas.
5. Preserve negrito, itálico, sublinhado, tabelas, imagens e separação entre texto de referência e questões quando suportado.
6. Relate ambiguidades de parsing para revisão humana; não invente alternativas, gabaritos ou limites de questão.
7. Teste documentos válidos, corrompidos, grandes, com tabelas, imagens, formatação e padrões ambíguos.

## Fluxo de revisão
- Verifique transições de estado permitidas no código/requisitos.
- Exija role autorizada no servidor.
- Registre decisão, observação, autor e timestamp no histórico.
- Não permita que edição comum apague ou reescreva histórico.
- Trate anulação/recurso como eventos auditáveis e preserve gabarito preliminar/definitivo.

## Testes de aceitação
- Importação preview → confirmação cria registros esperados uma única vez.
- Reenvio não duplica sem intenção.
- Tenant A não lê/edita questão de B.
- Revisor não altera recursos fora do escopo autorizado.
- Vínculos de textos de referência permanecem consistentes após criar, editar e excluir vínculo.
