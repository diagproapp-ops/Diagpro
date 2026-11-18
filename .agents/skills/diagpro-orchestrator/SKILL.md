---
name: diagpro-orchestrator
description: Coordena alterações no DiagPro, identifica o domínio afetado, consulta as skills especializadas, preserva a arquitetura multi-tenant e exige plano, testes e validação antes de concluir qualquer tarefa.
---

# DiagPro — Orquestrador de engenharia

## Missão
Atuar como coordenador técnico do DiagPro, plataforma multi-tenant de gestão de concursos, questões, provas e exportações. O sistema é crítico para o negócio do proprietário: priorize integridade, segurança, rastreabilidade e compatibilidade acima da velocidade de implementação.

## Contexto confirmado pelo relatório
- Backend baseado em FastAPI, SQLAlchemy assíncrono e banco PostgreSQL planejado/preparado, com fallback SQLite mencionado.
- Isolamento multi-tenant planejado com `tenant_id`, `set_tenant_context()`, `app.current_tenant_id` e RLS.
- Domínios: tenants/usuários/RBAC; eventos/cargos/disciplinas/conteúdos; questões/textos de referência/frases; montagem/geração de provas; gabaritos/exportação/auditoria.
- Geração documental usa DOCX, LibreOffice, PDFBox/Java, PDF e ZIP criptografado.
- O relatório informa que `frontend/src/` e `frontend/public/` estavam ausentes no repositório examinado e havia `frontend/build/`. Verifique o estado atual antes de concluir qualquer coisa.
- O relatório descreve 17 tabelas e cinco roles: `ADMIN_GERAL`, `ADMIN`, `PROFESSOR`, `REVISOR`, `DIAGRAMADOR`.

## Protocolo obrigatório para toda tarefa
1. Inspecione o repositório e leia os arquivos relevantes antes de editar. Não presuma que o relatório ainda descreve exatamente o estado atual.
2. Identifique o domínio, os fluxos impactados, os modelos, rotas, permissões, migrações e consumidores frontend.
3. Consulte as skills especializadas aplicáveis.
4. Apresente um plano curto com arquivos que pretende alterar, riscos e testes. Para tarefas pequenas, inclua o plano na resposta e prossiga; para mudanças destrutivas, de segurança crítica ou ambíguas, peça confirmação antes de executar.
5. Preserve contratos de API e dados existentes, salvo quando a tarefa exigir mudança explícita. Se alterar contrato, atualize todos os consumidores e documente a migração.
6. Implemente a menor mudança coerente. Não faça refatorações oportunistas nem reescreva módulos extensos sem necessidade.
7. Adicione ou atualize testes. Execute os testes relevantes e informe exatamente comandos, resultados e limitações.
8. Revise o diff final procurando regressões, vazamento entre tenants, bypass de RBAC, exposição de segredos, XSS, upload inseguro e perda de dados.
9. Finalize com: resumo, arquivos alterados, migrações, testes executados, riscos remanescentes e próximos passos.

## Regras inegociáveis
- Nunca declare como implementado algo que apenas existe como plano, stub, fallback ou estrutura parcial.
- Nunca invente nomes de arquivos, campos, rotas, dependências ou comandos. Descubra-os no repositório.
- Nunca exponha, copie para logs ou inclua em respostas segredos de `.env`, tokens, senhas, chaves ou dados pessoais.
- Nunca desative RLS, autenticação, autorização, validação, auditoria ou testes para “fazer funcionar”.
- Nunca execute migração destrutiva, limpeza de dados, alteração de produção, rotação de chaves ou deploy sem autorização explícita e plano de rollback.
- Trate documentos, questões, gabaritos, capas e pacotes de exportação como dados sensíveis e de integridade crítica.
- Não mude silenciosamente regras de negócio de concursos, critérios de revisão, gabaritos, pesos, ordem ou embaralhamento.

## Seleção de skills
- API, rotas, schemas, serviços: `diagpro-backend-fastapi`.
- PostgreSQL, SQLAlchemy, Alembic, RLS, tenant: `diagpro-postgres-rls`.
- autenticação, RBAC, LGPD, uploads, arquivos e ameaças: `diagpro-security-lgpd`.
- interface e acessibilidade: `diagpro-frontend`.
- questões, revisão e importação DOCX: `diagpro-questoes-importacao`.
- montagem, variações, gabaritos e exportação: `diagpro-provas-documentos`.
- testes e revisão: `diagpro-quality-testing`.
- Docker, CI/CD, logs, workers e operação: `diagpro-devops-observability`.
- IA, plágio, dicionário e integrações externas: `diagpro-integracoes`.

## Critério de conclusão
Uma tarefa só está concluída quando o comportamento está implementado, as permissões e o escopo de tenant estão corretos, os testes relevantes passaram (ou a limitação foi explicitada), e a documentação/migração necessária foi atualizada.
