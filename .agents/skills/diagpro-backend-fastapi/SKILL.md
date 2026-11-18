---
name: diagpro-backend-fastapi
description: Desenvolve e mantém o backend FastAPI do DiagPro, incluindo rotas, dependências, schemas, serviços assíncronos, tratamento de erros e contratos de API.
---

# Backend FastAPI do DiagPro

## Contexto
O relatório identifica `backend/app/` como núcleo FastAPI, com routers registrados em `main.py`, SQLAlchemy Async, autenticação em `auth.py`, autorização/utilitários em `security.py` e domínios em `routes/`. Confirme a estrutura e versões reais no repositório.

## Procedimento
1. Inspecione `main.py`, a rota, schemas, modelos, dependências e testes relacionados.
2. Determine autenticação, role e tenant exigidos pelo endpoint. Toda rota autenticada deve usar dependências consistentes; não confie em `tenant_id` enviado pelo cliente.
3. Mantenha handlers assíncronos quando acessarem I/O assíncrono. Não misture sessões sync/async nem bloqueie o event loop.
4. Separe validação HTTP, regra de negócio e persistência quando isso combinar com a arquitetura existente. Evite abstrações desnecessárias.
5. Use schemas de entrada/saída explícitos; não serialize modelos ORM indiscriminadamente nem exponha campos internos, credenciais ou dados bancários.
6. Padronize status HTTP, mensagens de erro e paginação conforme padrões já existentes.
7. Garanta que transações sejam delimitadas e revertidas em falha. Não confirme parcialmente operações que precisam ser atômicas.
8. Atualize testes de sucesso, validação, não autenticado, role proibida, tenant divergente e registros inexistentes.
9. Atualize documentação OpenAPI ou documentação do projeto quando o contrato mudar.

## Domínios conhecidos
`admin_clients.py`; `routes/auth.py`, `users.py`, `company.py`, `eventos.py`, `cargos.py`, `cargos_import.py`, `conteudos.py`, `templates.py`, `questoes.py`, `textos_referencia.py`, `frases.py`, `provas.py`, `provas_geracao.py`, `gabarito.py`, `exportacao.py`, `audit_log.py`, `ia_chat.py`, `plagio.py`, `dicionario.py`, `biblioteca.py`.

## Regras
- Não introduza acesso a banco sem escopo tenant.
- Não confie apenas em esconder botões no frontend para proteger endpoints.
- Não capture exceções genéricas retornando sucesso ou dados vazios.
- Não use `print()` para registrar dados operacionais ou sensíveis.
- Não mude nomes/formatos de rotas sem atualizar clientes.
- Não transforme endpoint stub em promessa de funcionalidade sem implementar persistência, autorização, testes e documentação.

## Verificação
Execute os testes focados e a suíte aplicável; rode lint/type checks existentes. Inspecione o diff e informe comandos e resultados reais. Se não houver testes/configuração, proponha a menor base coerente sem inventar comandos.
