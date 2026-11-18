---
name: diagpro-quality-testing
description: Cria e executa testes automatizados, testes de regressão, revisão de código e critérios de aceite do DiagPro, com foco em isolamento multi-tenant, RBAC e integridade de provas.
---

# Qualidade, testes e revisão

## Estratégia
O relatório propõe `pytest` para isolamento Tenant A/B, matriz RBAC dos cinco perfis, upload seguro e geração de provas/gabaritos. Transforme isso em suíte contínua, usando fixtures e infraestrutura reais do projeto.

## Pirâmide de testes
1. Unitários: regras de domínio, validação, códigos curtos, parsing e balanceamento.
2. Integração: rotas FastAPI, banco, transações, RLS, arquivos e serviços.
3. Contrato: schemas OpenAPI e consumidores frontend.
4. Ponta a ponta: fluxos críticos por perfil, se o framework frontend estiver disponível.
5. Segurança: testes negativos de autorização, tenant, uploads, XSS e abuso de endpoints.

## Matriz mínima
Para cada endpoint sensível, teste:
- sem token;
- token inválido/expirado;
- usuário inativo;
- cada role relevante;
- tenant correto e incorreto;
- recurso de evento/cargo alheio;
- payload inválido e limites;
- estado de negócio inválido.

## Fluxos críticos
- onboarding de tenant e criação do admin inicial;
- cadastro público de colaborador inativo e aprovação;
- evento → cargo → disciplinas → conteúdos;
- questão manual e importação DOCX preview/confirm;
- revisão e histórico;
- montagem, simulação, variações e gabaritos;
- geração DOCX/PDF/capa/ZIP e download autorizado;
- auditoria e falhas de exportação.

## Regras de execução
- Descubra os comandos e configurações existentes antes de executar.
- Nunca use banco de produção em testes.
- Use dados sintéticos; nunca copie dados pessoais reais para fixtures.
- Testes RLS devem conectar com role runtime real, não superuser/owner que possa ignorar políticas.
- Não enfraqueça assertions para fazer a suíte passar.
- Testes flaky precisam de causa raiz; não os ignore.
- Registre o comando, resultado, duração se relevante e dependências externas ausentes.

## Revisão de diff
Verifique regressões funcionais, autorização, tenant, SQL injection, XSS, path traversal, segredos, dados sensíveis em logs, migrações, compatibilidade e cobertura dos casos críticos.
