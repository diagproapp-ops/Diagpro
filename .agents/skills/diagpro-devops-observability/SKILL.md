---
name: diagpro-devops-observability
description: Gerencia Docker, configuração de ambientes, CI/CD, migrações operacionais, workers, logs estruturados, métricas, health checks, backups e deploy do DiagPro.
---

# DevOps e observabilidade

## Contexto do relatório
O plano cita Docker Compose, PostgreSQL, Dockerfile multi-stage com Python/JRE/LibreOffice, CI com `ruff`, `pytest`, `bandit`, `pip-audit`, `gitleaks`, logs JSON com `request_id` e `tenant_id`, e workers ARQ/Celery + Redis para geração pesada.

## Configuração
- Separe desenvolvimento, teste, staging e produção.
- Use `.env.example` apenas com placeholders; segredos reais ficam no gerenciador de segredos/ambiente.
- Fixe versões de imagens e dependências; mantenha lockfile.
- Health checks devem distinguir processo vivo de dependências prontas.
- Não exponha PostgreSQL, Redis, serviços internos ou diretórios de artefatos publicamente sem necessidade.

## Migrações e dados
- Migrações Alembic devem ser revisadas, versionadas e testadas em banco descartável e cópia representativa.
- Antes de mudança em produção: backup verificado, janela, plano de rollback e aprovação.
- Nunca execute migração destrutiva ou conversão SQLite→PostgreSQL em produção sem autorização explícita.
- Documente compatibilidade entre versão da aplicação e revisão do banco.

## CI/CD
Pipeline sugerido, adaptado aos comandos reais:
1. lint/format;
2. testes unitários e integração;
3. testes RLS com role runtime;
4. análise estática e dependências vulneráveis;
5. secret scanning;
6. build reproduzível;
7. deploy controlado em staging;
8. smoke tests;
9. promoção manual/guardada para produção.

## Observabilidade
- Logs JSON com `timestamp`, `level`, `service`, `environment`, `request_id`, `tenant_id` quando seguro, `user_id` interno e evento.
- Nunca registrar senha, token, chave, CPF completo, PIX ou conteúdo confidencial.
- Métricas: latência, taxa de erro, conexões DB, filas, jobs de exportação, conversões PDF, falhas e retries.
- Tracing/correlation id entre API, worker e geração documental.
- Alertas para falha de exportação, fila parada, falhas de login anormais e indisponibilidade do banco.

## Workers
Se introduzir fila, defina estados, idempotência, retry limitado, backoff, timeout, cancelamento, limpeza e persistência do progresso. SSE/WebSocket só após definir autorização e escopo do job.

## Operação
Forneça comandos exatos apenas após conferir arquivos e ambiente. Não afirme que deploy, backup ou rollback ocorreu sem evidência de execução.
