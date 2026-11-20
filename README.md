# DiagPro

**Sistema de gestão de bancas organizadoras, concursos públicos, questões, provas e gabaritos.**

O **DiagPro** é uma plataforma multi-tenant voltada à gestão de concursos públicos e avaliações, cobrindo desde a administração das bancas organizadoras (clientes) e estruturação dos eventos/editais até a elaboração, importação, revisão, montagem e geração automatizada de provas, capas em PDF e gabaritos.

> **Nota de transparência técnica:** Este documento reflete exclusivamente o que foi verificado diretamente no código-fonte, nas migrações e na configuração atuais do repositório (revisão de 19/11/2026, após as fases de segurança 0, 1a, 1b, 2a e 2b e o ajuste de gestão multi-cliente). Itens estruturados ou pendentes de validação em execução estão explicitamente sinalizados. Ao longo do texto, **"inspecionado"** significa lido no código e **"testado"** significa exercitado em execução, conforme registrado na [Seção 16](#16-testes-e-validação).

---

## Sumário

1. [Visão Geral e Objetivos](#1-visão-geral-e-objetivos)
2. [Estado Atual das Funcionalidades](#2-estado-atual-das-funcionalidades)
3. [Fluxo Operacional do Sistema](#3-fluxo-operacional-do-sistema)
4. [Perfis de Acesso e Responsabilidades (RBAC)](#4-perfis-de-acesso-e-responsabilidades-rbac)
5. [Arquitetura Técnica](#5-arquitetura-técnica)
6. [Tecnologias e Dependências Identificadas](#6-tecnologias-e-dependências-identificadas)
7. [Estrutura de Diretórios Real](#7-estrutura-de-diretórios-real)
8. [Modelo de Dados](#8-modelo-de-dados)
9. [Principais Módulos do Backend](#9-principais-módulos-do-backend)
10. [Principais Endpoints da API](#10-principais-endpoints-da-api)
11. [Banco de Questões, Importação DOCX e Revisão](#11-banco-de-questões-importação-docx-e-revisão)
12. [Montagem, Geração de Provas, Gabaritos e Exportação](#12-montagem-geração-de-provas-gabaritos-e-exportação)
13. [Integrações Externas](#13-integrações-externas)
14. [Segurança e Isolamento Multi-Tenant](#14-segurança-e-isolamento-multi-tenant)
15. [Instalação, Variáveis de Ambiente e Execução](#15-instalação-variáveis-de-ambiente-e-execução)
16. [Testes e Validação](#16-testes-e-validação)
17. [Limitações Conhecidas e Roadmap Técnico](#17-limitações-conhecidas-e-roadmap-técnico)
18. [Diretrizes para Desenvolvimento e Contribuição](#18-diretrizes-para-desenvolvimento-e-contribuição)

---

## 1. Visão Geral e Objetivos

O DiagPro centraliza o ciclo operacional de bancas organizadoras de concursos públicos e processos seletivos:

- Administrar múltiplos clientes/bancas (**multi-tenancy** em PostgreSQL com Row-Level Security e **cifra de campos com chave por cliente**).
- Estruturar concursos (**Eventos**), **Cargos**, **Disciplinas** e **Conteúdos Programáticos** com metas por professor.
- Manter um **Banco de Questões** (múltipla escolha, certo/errado, discursiva e subjetiva) com textos de referência, imagens e trilha de revisão.
- Automatizar a **importação de questões via DOCX**, montagem de cadernos, simulações, geração de variações e exportação de **DOCX, PDF, capas AcroForm e pacotes ZIP protegidos por senha**.
- Registrar auditoria de geração de provas (`audit_log_geracao`).

Premissa de projeto: questões, gabaritos, provas, capas, credenciais e dados de colaboradores são confidenciais. Tudo o que vai para o banco e para o disco é cifrado, e nenhuma prova gerada é guardada no servidor.

---

## 2. Estado Atual das Funcionalidades

Classificação adotada:
- **Implementada e verificada:** comportamento presente no código e exercitado em execução (ver [Seção 16](#16-testes-e-validação)).
- **Implementada parcialmente:** existe implementação no código, porém com lacunas, mocks ou pendências.
- **Estruturada, mas não validada:** modelos, scripts ou configurações existem no repositório, mas não foram executados/validados em runtime.
- **Planejada:** descrita no roadmap, sem implementação no código atual.
- **Não identificada:** sem evidência suficiente no repositório atual.

| Funcionalidade | Classificação | Evidência / Observação |
| :--- | :--- | :--- |
| PostgreSQL multi-tenant com RLS | **Implementada e verificada** | Banco único da aplicação (sem fallback SQLite). RLS `ENABLE` + `FORCE` em 24 tabelas, **sem cláusula de bypass por variável de sessão**. Testado com a role de runtime: isolamento entre tenants, *fail-closed* sem contexto e tentativa de bypass bloqueada. |
| Cifra de campos (AES-256-GCM, chave por tenant) | **Implementada e verificada** | `backend/app/field_crypto.py`: 122 colunas sensíveis cifradas, incluindo enunciados, alternativas, gabarito (`correta`, `valor_correto`) e dados pessoais. Varredura no banco real: 4.034 valores, nenhum em texto claro. |
| Arquivos cifrados e URLs assinadas | **Implementada e verificada** | `backend/app/secure_files.py`: imagens, avatares, logos, capas, templates e CSV de candidatos cifrados por tenant; entrega por URL assinada de 5 min. Pastas públicas `/static` e `/avatars` removidas. |
| Provas geradas sem armazenamento | **Implementada e verificada** | Saídas criadas em pasta temporária privada por requisição e apagadas ao final; ZIP do lote protegido pela senha do evento. Testado ponta a ponta numa cópia do banco. |
| Autenticação JWT (`HS256`) + `bcrypt` | **Implementada e verificada** | `backend/app/auth.py`, `routes/auth.py`, `dois_fatores.py`. **2FA (TOTP) obrigatório para todos**: senha certa só gera um passe de 5 min; acesso só com token emitido após o código do autenticador (ou código de recuperação de uso único). Testado via API e pela tela (cadastro com QR Code, códigos de recuperação, novo login, reset pelo administrador). Testado: login válido (200), senha errada (401), inativo (403), token adulterado (401), limite de 10 tentativas/60 s (429). |
| reCAPTCHA no login | **Implementada e verificada** | Falha fechada: sem `RECAPTCHA_SECRET_KEY`, sem resposta do Google (timeout 5 s) ou com erro, o login é recusado. `DIAGPRO_RECAPTCHA_DESATIVADO=1` existe só para testes automatizados e registra um aviso na inicialização. Token falso recusado na API real (400). |
| Gestão de Tenants e Dashboard (`administrador geral`) | **Implementada e verificada** | `admin_clients.py` sempre via role de plataforma; criação de cliente, duplicidade de domínio (400), listagem e dashboard testados. Visão global ou **cliente em gestão** escolhido no topo da tela (cabeçalho `X-Tenant-Id`, ver [Seção 14](#14-segurança-e-isolamento-multi-tenant)), testado. O admin criado para um cliente recebe senha aleatória, exibida uma única vez. |
| Gestão de Usuários e Cadastro Público | **Implementada parcialmente** | `routes/users.py`. Testados: bloqueio de perfis administrativos no cadastro público, criação/edição pelo admin do cliente e recusa de e-mail duplicado sem diferenciar maiúsculas (índice cego). Testados também: admin de cliente restrito aos usuários do próprio cliente, listagem de todos os clientes pelo `administrador geral` na visão global e username/e-mail duplicado entre clientes recusado com 400. |
| CRUD de Eventos, Cargos, Disciplinas e Conteúdos | **Implementada parcialmente** | Fluxos principais testados (criar/editar/listar). O CRUD completo e o isolamento entre tenants de todos os recursos não têm teste automatizado. |
| Banco de Questões, Textos de Referência e Revisão | **Implementada parcialmente** | Criar, editar e revisar questões dos 4 tipos (múltipla escolha, Certo/Errado com imagem por item, discursiva e subjetiva) e textos de referência (texto e imagem) testados via API num banco de teste, com os mesmos envios das telas; telas abertas sem erro em navegador automatizado. O salvamento por cliques reais na interface não foi exercitado. |
| Importação de Questões via DOCX | **Implementada parcialmente** | Imagens extraídas vão direto para o armazenamento cifrado; a confirmação aceita só referências de arquivo do próprio cliente (testado). A extração DOCX em si não tem teste automatizado. |
| Montagem, Simulação e Geração de Provas/Gabaritos | **Implementada parcialmente** | Ponta a ponta testado num banco de teste com dados sintéticos (19/11/2026): montagem, lote ZIP AES com PDF e DOCX legíveis (acentos, alternativas, texto de referência), gabarito batendo com a ordem impressa da alternativa correta, ZIP de gabaritos. Prova pronta e gabarito só com a senha do evento. Geração das provas reais não executada (exige a senha do evento). Sorteios (ordem das questões, alternativas e letras do gabarito) derivam de uma semente secreta gravada (cifrada) na montagem: cada exportação da mesma montagem sai idêntica e o gabarito não é previsível; montagens anteriores a 19/11/2026 mantêm a fórmula antiga para não mudar provas já exportadas. Checagem antes de exportar (bloqueios e avisos), relatório no ZIP, nomes únicos por variação ("PADRÃO" ou "Tipo A"...), versão com gabarito marcado identificada, auditoria com SHA-256, padrão de exportação por evento (só sugestão) e "Atualizar questões da montagem" sem novo sorteio. Certo/Errado: comando sem número e itens numerados na sequência da prova toda, gabarito C/E por item. Subjetiva: enunciado e a quantidade de linhas definida na questão (padrão 10). Alternativas e itens vindos do editor (HTML) saem com a formatação, sem tags. |
| Auditoria de Geração (`audit_log_geracao`) | **Implementada parcialmente** | Gravação e filtro por usuário (índice cego) testados; cobre geração, não leitura/edição geral. |
| Assistente de IA (Claude ou OpenAI) | **Implementada e verificada** | Rascunho de questão, revisão, alternativas erradas, justificativa, melhoria de texto e chat no editor. Desligado por padrão; a plataforma e a banca precisam ligar. Testado com provedor falso local pelos dois SDKs; chamada real depende da chave do provedor. |
| Verificação de Plágio (Bing) | **Implementada parcialmente** | Autenticada, rate limit 20/60 s; chamada externa não testada. |
| Dicionário (`dicio.com.br`) | **Implementada parcialmente** | Scraping HTML via regex; não testado. |
| Biblioteca de Questões (`/api/biblioteca`) | **Implementada e verificada** | Busca em conteúdo cifrado (decifra só as questões do próprio cliente na memória); isolamento tenant 1 × tenant 2 testado. |
| Frontend Web (React/TS) | **Implementada parcialmente** | `frontend/src/` versionado neste repositório. Rotas de montagem, geração, exportação, gabaritos, templates, questões (criar/editar/revisar), textos de referência, "Meus Conteúdos" e cadastro público registradas em `App.tsx`; telas adaptadas ao tema ativo. Verificado por `tsc --noEmit` e pelas chamadas de API de cada tela; os fluxos que gravam dados não foram exercitados pela interface. |
| Suíte de Testes Automatizados | **Implementada parcialmente** | 31 testes `pytest` (2FA, política de senha, sessão, configurações, segurança, RBAC, RLS, cifra, arquivos, logs, gestão multi-cliente, tipos de questão, senha do evento, CORS, semente, exportação e renderização), executados por `scripts/run_tests.py` num banco descartável. Cobertura de isolamento ainda parcial. |
| Rate Limiting | **Implementada e verificada** | `rate_limit.py` (memória; Redis se `REDIS_URL`). Login 10/60 s; validar senha, lote e ZIP de gabaritos 5/60 s; cadastro 5/60 s; IA/plágio 20/60 s. |
| CI/CD | **Estruturada, mas não validada** | `.github/workflows/ci.yml` (PostgreSQL 16, chave mestra efêmera, migrações, RLS, roles, `pytest`). Execuções no GitHub Actions não foram verificadas. |
| Filas assíncronas e Object Storage (S3/MinIO) | **Estruturada, mas não validada** | `jobs.py` (registro em memória) e `storage.py` (backend S3 depende de `boto3`, ausente). A rota de exportação assíncrona foi removida por não funcionar. |

---

## 3. Fluxo Operacional do Sistema

1. **Cadastro do Cliente (`Tenant`)**: O `administrador geral` registra a banca organizadora (`/admin/clients`) e cria o usuário `administrador` do tenant.
2. **Equipe e Permissões**: O `administrador` do tenant cadastra usuários internos ou aprova cadastros externos (`/users/register`) de `professor`, `revisor` e `diagramador`.
3. **Estruturação do Evento**: Criação do concurso/edital (`/eventos`), cadastro manual ou via CSV de cargos (`/eventos/{event_id}/cargos`, `/eventos/{event_id}/cargos/import-csv`), upload de capas PDF (`/eventos/{event_id}/cargos/upload-capa-pdf`) e cadastro de conteúdos programáticos (`/conteudos/eventos/{evento_id}/conteudos`, `.../conteudos/csv`) vinculados a professores.
4. **Elaboração e Revisão**: Professores criam ou importam questões (`.docx`) e textos de referência; revisores analisam e registram pareceres em `HistoricoRevisaoQuestao`.
5. **Montagem e Simulação**: Diagramadores/administradores montam a prova por cargo (`/provas/eventos/{id_evento}/provas-montadas/{id_cargo}`), definem variações e embaralhamento (`/eventos/{event_id}/provas/definir-geracao`) e simulam frases/itens Certo-Errado.
6. **Geração e Exportação**: Após validação da senha do evento (`/api/export/eventos/{evento_id}/validar-senha`), o lote (`gerar-arquivos-multiplos`) gera os cadernos DOCX/PDF, preenche capas PDF via Java PDFBox e entrega um ZIP protegido pela senha do evento. Nada fica armazenado no servidor; a prova pode ser regerada a partir do banco.

---

## 4. Perfis de Acesso e Responsabilidades (RBAC)

Definidos em `backend/app/roles.py` (`UserRole`):

| Perfil (`UserRole`) | Escopo | Responsabilidades Previstas |
| :--- | :--- | :--- |
| `administrador geral` | Global (todos os tenants) | Gerenciar clientes/tenants (`/admin/clients`), dashboard consolidado, criação de administradores por tenant e usuários de todos os clientes. Para operar dentro de um cliente (eventos, conteúdos, provas), escolhe o **cliente em gestão** e passa a ver e gravar somente nele. |
| `administrador` | Tenant | Gerenciar usuários do seu cliente, dados da empresa (`company_data`), eventos, cargos e configurações. |
| `professor` | Tenant | Elaborar e editar questões, textos de referência e gerenciar seus conteúdos atribuídos (`/conteudos/meus`). |
| `revisor` | Tenant | Revisar questões submetidas e registrar histórico de aprovação/observações (`HistoricoRevisaoQuestao`). |
| `diagramador` | Tenant | Gerenciar templates, montar provas, simular variações e gerar/exportar arquivos finais e gabaritos. |

A aplicação dos perfis é feita pela dependência `require_roles` (`backend/app/security.py`) e por `get_admin_user` / `get_admin_geral_user`. Um administrador de cliente só cria, edita e exclui usuários do próprio cliente e não pode atribuir o perfil `administrador geral`. O `administrador geral` não pertence a nenhum cliente (`tenant_id` nulo) e nunca recebe um cliente padrão; mover usuários entre clientes só é permitido na visão global. O teste `test_rbac_matrix_five_roles` cobre um subconjunto da matriz perfil × rota; as demais combinações foram apenas inspecionadas.

---

## 5. Arquitetura Técnica

O projeto encontra-se em transição entre uma aplicação desktop Python legada (`core/` com `customtkinter`/`tkinter`) e uma arquitetura Web Full-Stack (`backend/` + `frontend/`), compartilhando o motor de geração e parsing de documentos:

```text
+-------------------------------------------------------+
|              FRONTEND (React 18 / TS / MUI)           |
|   frontend/src/ (local, não versionado) + build/      |
+---------------------------+---------------------------+
                            | HTTPS / REST + URLs assinadas
+---------------------------v---------------------------+
|             BACKEND API (FastAPI / Uvicorn)           |
|  - Auth JWT + bcrypt, RBAC, rate limit, logs redigidos|
|  - field_crypto: AES-256-GCM por tenant (ORM)         |
|  - secure_files: arquivos cifrados + URL assinada     |
+-------------+---------------------------+-------------+
              |                           |
              v                           v
+---------------------------+  +------------------------+
|  Núcleo Core (core/)      |  |  Motor PDFBox (Java)   |
|  - DocumentGenerator      |  |  PreencheCapaPDF_JSON  |
|  - DocxParser             |  |  pdfbox-app-3.0.5.jar  |
|  - LibreOffice (PDF)      |  +------------------------+
+-------------+-------------+
              | SQLAlchemy Async + TLS verify-full
+-------------v-----------------------------------------+
|   PostgreSQL 16 (somente; RLS forçado, sem bypass)    |
|   - diagpro_runtime: requisições de um tenant         |
|   - diagpro_platform (BYPASSRLS): login/admin geral   |
+-------------------------------------------------------+
```

Fora do projeto e do banco ficam a chave mestra, a chave de backup, a CA/certificados TLS e os backups cifrados (`%LOCALAPPDATA%\DiagPro\secrets` e `%LOCALAPPDATA%\DiagPro\backups`).

---

## 6. Tecnologias e Dependências Identificadas

- **Backend Python** (`backend/requirements.txt`, 30 pacotes, versões fixadas exceto `redis>=5.0`): FastAPI, Starlette, Uvicorn, SQLAlchemy Async (`SQLAlchemy[asyncio]`, `greenlet`, `asyncpg`), `psycopg2-binary` (Alembic e scripts), Alembic, Pydantic, `email_validator`, `python-jose`, `passlib[bcrypt]`/`bcrypt`, `cryptography` (AES-GCM, HKDF), `python-multipart`, `python-docx`, `pypdf`, `pdfrw`, `reportlab`, `pillow`, `beautifulsoup4`, `pyzipper`, `openai`, `requests`, `httpx`, `redis`, `python-dotenv`, `pytest`, `pytest-asyncio`.
  - *Versões verificadas no `.venv` da raiz:* Python `3.11.0`, Uvicorn `0.37.0`, Alembic `1.20.1`, pytest `9.2.0`.
  - *Divergências conhecidas:* `boto3` (backend S3 de `storage.py`) não consta no arquivo; `redis` não está instalado no `.venv` local (o rate limit usa memória).
  - `aiosqlite` foi removido: o sistema não usa mais SQLite.
- **Processamento de Documentos Externo**: LibreOffice (`soffice.exe` para DOCX → PDF, com até 3 tentativas por conversão) e Java + **Apache PDFBox 3.0.5** (`backend/app/pdfbox-app-3.0.5.jar`, `json.jar`).
- **Frontend (`frontend/package.json`)**: React `18.2.0`, TypeScript `4.9.5`, Material UI v7, TipTap v3, `@dnd-kit`, `axios`, `react-router-dom` v7, `html2pdf.js`, `react-markdown`, `react-google-recaptcha`.
- **Infraestrutura**: `docker-compose.yml` com `postgres:16-alpine`, `redis:7-alpine` e `minio/minio:latest`, todos publicados **somente em `127.0.0.1`** (PostgreSQL na porta `5435`). `Dockerfile` da API (`python:3.11-slim`, OpenJDK 17, LibreOffice Writer, usuário não-root, healthcheck em `/health`). CI em `.github/workflows/ci.yml`.

---

## 7. Estrutura de Diretórios Real

```text
DiagPro/
├── .github/workflows/ci.yml      # CI: PostgreSQL 16 + chave mestra efêmera + Alembic + RLS + roles + pytest
├── alembic/
│   ├── env.py                    # Só PostgreSQL; aplica o TLS de DB_SSLMODE/DB_SSL_ROOT_CERT
│   └── versions/                 # 15cec84ab488 -> 24cbf7a7b399 -> c3f1a9d2b7e4 (RLS sem bypass) -> e7b2d4f8a1c6 (cifra de campos)
│                                 #   -> a9d4c2e6f0b1 (trava de troca de tenant sem recifra; códigos únicos por cliente)
│                                 #   -> c5e8f1a3b9d2 (imagem cifrada por item de Certo/Errado)
│                                 #   -> d8b2f4a6c1e3 (padrão de exportação por evento, cifrado)
│                                 #   -> e9c3a5b7d2f4 (2FA: segredo TOTP e códigos de recuperação cifrados)
│                                 #   -> f1a7c3e5b9d2 (política de senha: validade, troca obrigatória, histórico cifrado)
│                                 #   -> a2b4c6d8e0f1 (configurações da plataforma e de cada banca, cifradas, com RLS)
├── alembic.ini
├── .env.example                  # Modelo de variáveis (somente placeholders)
├── Dockerfile                    # Imagem da API (Python 3.11, Java 17, LibreOffice)
├── pytest.ini
├── backend/
│   ├── app/
│   │   ├── routes/               # Routers FastAPI por domínio (inclui files.py: entrega por URL assinada)
│   │   ├── admin_clients.py      # Gestão de clientes (administrador geral)
│   │   ├── auth.py               # JWT, bcrypt, get_current_user (runtime por tenant; plataforma só p/ admin geral; X-Tenant-Id)
│   │   ├── database.py           # Engines runtime/plataforma, TLS obrigatório, set_tenant_context
│   │   ├── db_models.py          # 25 modelos ORM; colunas sensíveis com tipo Ciphertext + índices cegos
│   │   ├── field_crypto.py       # Cifra de campos AES-256-GCM por tenant, índices cegos, eventos do ORM
│   │   ├── secure_files.py       # Arquivos cifrados por tenant, URLs assinadas, templates, pasta por requisição
│   │   ├── log_redaction.py      # Filtro que mascara senhas, assinaturas, tokens e caminhos nos logs
│   │   ├── security.py           # require_roles, get_tenant_db, evento_autorizado, senha do evento, helpers de caminho
│   │   ├── verificacao_prova.py  # Checagem da prova montada antes de exportar (bloqueios e avisos)
│   │   ├── dados_prova.py        # Completa a cópia da montagem (tipo, itens Certo/Errado, linhas)
│   │   ├── configuracoes.py      # Configurações da plataforma e da banca (padrões, limites, cache)
│   │   ├── assistente_ia.py      # IA: provedores (Anthropic/OpenAI), pedidos, formatos de resposta, limites e registro de uso
│   │   ├── notificacoes.py       # Avisos (sino + e-mail): preferências, fila SMTP com novas tentativas
│   │   ├── sessoes.py            # Acessos: abrir/validar/encerrar, alerta de aparelho novo
│   │   ├── fluxo_revisao.py      # Estados da revisão, envio, decisão, reabertura e avisos
│   │   ├── versoes_questao.py    # Versões das questões e busca local de parecidas
│   │   ├── backups.py, saude.py  # Backups cifrados agendados e painel de saúde
│   │   ├── lgpd.py               # Exportação, anonimização, aceite de termos e retenção
│   │   ├── entregas.py           # Entrega de pacotes por link com código, validade e limite
│   │   ├── estatisticas.py       # Análise de itens pós-prova (só agregados)
│   │   ├── politica_senha.py     # Política de senha (valores vindos das configurações)
│   │   ├── auditoria_exportacao.py  # Registro cifrado de cada exportação (quem, quando, opções, SHA-256)
│   │   ├── rls_policies.sql      # Políticas RLS (24 tabelas, sem bypass)
│   │   ├── rate_limit.py, jobs.py, storage.py, models.py, roles.py, ...
│   │   ├── utils_crypto.py       # Camada Fernet LEGADA, desativada (funções sem efeito; mask_pii)
│   │   └── PreencheCapaPDF_JSON_PDFBox.java
│   └── requirements.txt
├── core/                         # Núcleo legado desktop + motor de documentos/parser (usado pela API)
├── frontend/                     # React/TS (CRA); src/App.tsx registra as rotas, src/api.ts envia token e X-Tenant-Id
├── scripts/
│   ├── setup_postgres_roles.py   # Cria/ajusta diagpro_runtime e diagpro_platform; --rotate gera senhas no .env
│   ├── gen_pg_tls.py             # Gera CA privada e certificado TLS do PostgreSQL (fora do projeto)
│   ├── backup_crypto.py          # Cifra/decifra backups (AES-256-GCM em blocos, chave fora do projeto)
│   ├── reencrypt_fields.py       # Converte dados para a cifra de campos (executado na fase 1b)
│   ├── repair_nested_legacy_fernet.py  # Remove Fernet legado embutido em JSON (executado em 19/11/2026)
│   ├── run_tests.py              # Roda o pytest num banco descartável diagpro_test com chave mestra de teste
│   └── migrate_files_to_secure_store.py  # Move arquivos em claro para o armazenamento cifrado (executado na fase 2a)
├── tests/
│   ├── conftest.py               # Cliente ASGI, tokens e seed sintético (role de plataforma)
│   └── test_security_rbac_rls.py # 31 testes
├── docker-compose.yml            # PostgreSQL, Redis e MinIO (somente 127.0.0.1)
├── storage_data/                 # Arquivos cifrados (ignorado pelo Git)
├── templates_eventos/            # Templates DOCX cifrados (*.enc, ignorado pelo Git)
├── create_db.py                  # Script legado (SQLite), não usado pela API
└── update_password.py            # Utilitário pontual para senha de evento
```

Não existem mais `static/`, `avatars/`, `ProvasGeradas_DG/` nem `diagprooff.db`.

---

## 8. Modelo de Dados

Definido em `backend/app/db_models.py` (**17 tabelas** registradas em `Base.metadata`):

- **Multi-tenancy e Acesso:** `tenants` (`Tenant`, tabela raiz sem `tenant_id`), `users` (`User`, `tenant_id` nulo para `administrador geral`), `company_data` (`Company`).
- **Estrutura de Concursos:** `Eventos`, `Cargos`, `Disciplinas`, `DisciplinasDaProva`, `conteudos`.
- **Questões e Apoio:** `TextosReferenciaGeral`, `QuestoesBanco`, `OpcoesQuestao`, `ItensVerdadeiroFalso`, `DetalhesQuestaoDiscursiva`, `HistoricoRevisaoQuestao`.
- **Provas e Auditoria:** `ProvasMontadas`, `banco_frases`, `audit_log_geracao`.

### Colunas cifradas e índices cegos

- **122 colunas** são declaradas com o tipo `Ciphertext` e guardam `e1.<versão>.<AES-256-GCM>`: todo texto livre, conteúdo de questões/textos/provas, gabaritos (inclusive os booleanos `OpcoesQuestao.correta` e `ItensVerdadeiroFalso.valor_correto`), dados pessoais/bancários, dados de clientes, caminhos de arquivo e campos da auditoria.
- **Ficam em claro** apenas: chaves (PK/FK), `tenant_id`, códigos técnicos gerados (`identificador_*`, `codigo_*`), papéis/estados/tipos usados em autorização e fluxo, datas, números, `password_hash` (bcrypt) e `senha_evento` (bcrypt).
- **Índices cegos** (HMAC-SHA256, colunas `*_bidx`) permitem busca exata e unicidade sem expor o valor: `users.username/email` (escopo global, usado no login), `tenants.name/domain` (global), `users.full_name`, `banco_frases.categoria` e `frase_bidx`, `Disciplinas.nome_disciplina` e `audit_log_geracao.usuario/evento/cargo` (escopo por cliente: o mesmo valor em clientes diferentes gera índices diferentes).

### 25 modelos ORM × 24 tabelas com RLS

`rls_policies.sql` (e a revisão `c3f1a9d2b7e4`) aplicam `ENABLE` + `FORCE ROW LEVEL SECURITY` e a política `tenant_id = app.current_tenant_id` em **24** tabelas. A exceção é **`tenants`**, que não tem `tenant_id` porque define os próprios clientes.

- O acesso a `tenants` só ocorre pela role `diagpro_platform`, em rotas exclusivas do `administrador geral`. A camada de cifra também bloqueia sessões de runtime que tentem carregar linhas de `tenants`.
- Em `users`, linhas com `tenant_id` nulo (administrador geral) só são visíveis pela role `diagpro_platform`, que tem `BYPASSRLS`. Não existe bypass por variável de sessão.
- A revisão `a9d4c2e6f0b1` cria o gatilho `trg_exige_recifra_tenant` nas 16 tabelas: um `UPDATE` que troque `tenant_id` sem recifrar todas as colunas cifradas da linha é recusado pelo banco, inclusive para superusuário. Trocas de cliente feitas pelo ORM recifram automaticamente.
- `identificador_evento`, `identificador_cargo`, `identificador_conteudo` e `codigo_curto_questao` são únicos **por cliente** (`tenant_id` + código). Antes eram únicos no banco inteiro e dois clientes com o mesmo código geravam erro 500.

---

## 9. Principais Módulos do Backend

- `backend/app/main.py`: inicialização da API, nível de log (`DIAGPRO_LOG_LEVEL`, padrão `WARNING`), filtro de redação de logs, CORS (`CORS_ORIGINS`), cabeçalhos de segurança e `X-Request-ID`, `GET /health` e routers. Não há montagens de arquivos estáticos.
- `backend/app/database.py`: engine da role de runtime e engine da role de plataforma, ambas com TLS (`DB_SSLMODE`, padrão `verify-full`); `set_tenant_context` (contexto por transação, *fail-closed*); recusa iniciar sem PostgreSQL.
- `backend/app/field_crypto.py` e `db_models.py`: cifra/decifra transparente no ORM, índices cegos, tipo `Ciphertext` que recusa texto claro em SQL direto e bloqueio de linhas de outro tenant em sessões de runtime.
- `backend/app/secure_files.py` e `routes/files.py`: armazenamento cifrado de arquivos, URLs assinadas, validação de conteúdo de uploads, descarte de caminhos vindos do cliente e pasta temporária por requisição para o gerador.
- `backend/app/auth.py` e `backend/app/security.py`: autenticação JWT, usuário ativo, `require_roles`, `get_tenant_db`, `evento_autorizado`, helpers de caminho.
- `backend/app/log_redaction.py`: mascara senhas, assinaturas, tokens, caminhos e nomes de arquivo em todos os logs (inclusive no log de acesso do uvicorn).
- `core/document_generator.py` e `core/docx_parser.py`: geração de provas/gabaritos em DOCX/PDF e extração de documentos Word. Os `print` de depuração desses módulos viram logs DEBUG.

---

## 10. Principais Endpoints da API

Tabela conferida contra as rotas registradas em `app.routes` em 18/11/2026: **85 operações HTTP**, mais `/docs`, `/docs/oauth2-redirect`, `/redoc` e `/openapi.json`. Não há montagens públicas de arquivos.

| Prefixo / Módulo | Endpoints Principais |
| :--- | :--- |
| **Sistema** (`main.py`) | `GET /`, `GET /health` |
| **Arquivos** (`routes/files.py`) | `GET /api/files/{scope}/{name}?exp=&sig=` (URL assinada de vida curta; sem token) |
| **Auth** (`/auth`) | `POST /auth/login` |
| **Usuários** (`/users`) | `POST /users/register`, `GET /users/me`, `GET / POST /users/`, `PATCH / DELETE /users/{user_id}` |
| **Admin Tenants** (`admin_clients.py`) | `GET / POST /admin/clients`, `GET /admin/clients/dashboard`, `POST /admin/clients/{client_id}/create-admin`, `GET /admin/clients/{client_id}` |
| **Empresa** (`company.py`) | `GET / PUT /company` |
| **Eventos** (`/eventos`) | `GET / POST /eventos/`, `GET /eventos/{event_id}/detalhes`, `GET / PUT / DELETE /eventos/{event_id}` |
| **Cargos** (`cargos.py`, `cargos_import.py`) | `GET / POST /eventos/{event_id}/cargos`, `PUT / DELETE /cargos/{cargo_id}`, `POST /eventos/{event_id}/cargos/upload-capa-pdf`, `POST /eventos/{event_id}/cargos/import-csv` |
| **Conteúdos** (`/conteudos`) | `GET / POST /conteudos/eventos/{evento_id}/conteudos`, `POST /conteudos/eventos/{evento_id}/conteudos/csv`, `PUT / DELETE /conteudos/{conteudo_id}`, `GET /conteudos/meus` |
| **Questões** (`questoes.py`) | `GET / POST /eventos/{evento_id}/conteudos/{conteudo_id}/questoes`, `GET / PUT / DELETE .../questoes/{id_questao}`, `PATCH .../questoes/{id_questao}/revisao`, `GET .../questoes/{id_questao}/revisoes`, `POST .../importar-docx`, `POST .../importar-docx/confirmar` |
| **Textos de Referência** (`textos_referencia.py`) | `GET / POST /eventos/{evento_id}/conteudos/{conteudo_id}/textos-referencia`, `GET / PATCH / DELETE .../textos-referencia/{id_texto_ref}` |
| **Frases** (`/frases`) | `GET / POST /frases/`, `PUT / DELETE /frases/{frase_id}`, `POST /frases/import/` |
| **Templates** (`/api`) | `GET /api/eventos/{evento_id}/templates`, `POST .../templates/upload`, `GET / DELETE .../templates/{nome_arquivo}` |
| **Provas e Simulação** (`/provas`, `provas_geracao.py`) | `GET /provas/eventos/{id_evento}/cargos-com-status-prova`, `GET / POST / DELETE /provas/eventos/{id_evento}/provas-montadas/{id_cargo}`, `GET /provas/eventos/{id_evento}/disciplinas`, `GET /provas/eventos/{event_id}/cargos-quantidade-questoes`, `GET /eventos/{event_id}/cargos/provas-geracao`, `POST /eventos/{event_id}/provas/definir-geracao`, `POST /eventos/{event_id}/simular-frases/{cargo_id}`, `POST /eventos/{event_id}/simular-certo-errado/{cargo_id}` |
| **Gabaritos** (`/api/gabarito`) | `GET .../cargos/{cargo_id}/gabarito`, `GET .../cargos/{cargo_id}/variacoes`, `GET .../cargos/{cargo_id}/exportacoes`, `POST /api/gabarito/eventos/{evento_id}/exportar-gabaritos-zip` |
| **Exportação** (`/api/export`) | `POST .../eventos/{evento_id}/validar-senha`, `POST .../eventos/{evento_id}/cargos/gerar-arquivos-multiplos` (fluxo do frontend), `GET .../cargos/{cargo_id}/exportacoes`, `POST .../cargos/{cargo_id}/gerar-arquivos`, `POST .../cargos/{cargo_id}/exportar-gabarito`, `GET /api/export/download`, `GET /api/export/jobs/{job_id}` |
| **Auditoria** (`/admin/logs/geracao`) | `GET / POST /admin/logs/geracao/` |
| **Apoio / IA** (`/api`) | `POST /api/ia-chat`, `POST /api/check-plagio`, `POST /api/dicionario`, `POST /api/biblioteca` |

Removidos nas fases de segurança: `/static` e `/avatars` (públicos), `/debug_ping`, `/api/export/debug_export_ping`, `/api/export/download-zip` (entregava um ZIP sem senha gravado em disco) e `/api/export/.../gerar-arquivos-async` (nunca funcionou).

---

## 11. Banco de Questões, Importação DOCX e Revisão

- **Tipos suportados**: `MULTIPLA_ESCOLHA` (`OpcoesQuestao`), `CERTO_ERRADO` (`ItensVerdadeiroFalso`), `DISCURSIVA` e `SUBJETIVA` (`DetalhesQuestaoDiscursiva`).
- **Conteúdo cifrado**: enunciado, versão formatada, alternativas, indicação de correta, resposta esperada, justificativas e histórico de revisão são cifrados com a chave do cliente.
- **Imagens**: uploads de enunciado, alternativas e textos de referência têm extensão, tamanho e assinatura de conteúdo validados e vão para o armazenamento cifrado; a API devolve URLs assinadas no mesmo formato relativo que o frontend usa.
- **Importação DOCX**: `core/docx_parser.py` extrai texto, tabelas e imagens numa pasta temporária; as imagens são cifradas e a pré-visualização recebe URLs assinadas. Na confirmação, campos de caminho vindos do cliente só são aceitos se forem referências válidas do próprio cliente.
- **Revisão**: altera `status_revisao`/`observacao_revisor` e grava histórico em `HistoricoRevisaoQuestao`.

---

## 12. Montagem, Geração de Provas, Gabaritos e Exportação

- **Montagem**: `ProvasMontadas` guarda `blocos_questoes` e `metadados_prova` (cifrados) por evento/cargo.
- **Geração e Variações**: `provas_geracao.py` configura número de variações, embaralhamento e simulações. O CSV de candidatos (dados pessoais) é gravado cifrado.
- **Entrada do gerador**: imagens, logo, capas, templates e CSV são decifrados apenas numa pasta temporária privada da requisição (`secure_files.request_workdir`), apagada ao final mesmo em caso de erro. Campos de caminho que não sejam referências válidas do cliente viram vazio antes de chegar ao gerador.
- **Saídas**: DOCX, PDF (LibreOffice, até 3 tentativas), capas AcroForm (`PreencheCapaPDF_JSON_PDFBox.java`), gabaritos e ZIPs são criados na mesma pasta temporária, entregues em memória (`Cache-Control: private, no-store`) e apagados. O lote e o ZIP de gabaritos são protegidos com a senha do evento (AES, `pyzipper`).
- **Senha do evento**: comparada em tempo constante, com limite de 5 tentativas/60 s no lote, na validação e no ZIP de gabaritos.

---

## 13. Integrações Externas

- **Assistente de IA** (`assistente_ia.py`, rotas `/ia/*`): Claude pelo SDK `anthropic` (padrão `claude-opus-5-5`, saída em JSON com schema, `effort` médio e *fallback* de recusa do servidor) ou OpenAI pelo SDK `openai` (`json_schema` estrito, `store=false`). Provedor, modelo, chaves e limites ficam em Configurações > Plataforma > Inteligência artificial; a chave salva na tela fica cifrada e nunca volta para a tela (sem ela, usa `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` do servidor). O texto enviado sai para o provedor escolhido.
- **Bing Web Search API v7** (`plagio.py`): requer `BING_API_KEY`. O texto analisado sai do sistema para um serviço externo.
- **Google reCAPTCHA** (`routes/auth.py`): requer `RECAPTCHA_SECRET_KEY`; sem a chave ou sem resposta do Google, o login é recusado (*fail-closed*).
- **Dicio (`dicio.com.br`)** (`dicionario.py`): requisição HTTP e regex sobre HTML.

---

## 14. Segurança e Isolamento Multi-Tenant

**Banco de dados**
- Somente PostgreSQL; a API recusa iniciar sem `DATABASE_URL` PostgreSQL e sem `PLATFORM_DATABASE_URL` distinta.
- Conexões com TLS obrigatório: `pg_hba.conf` aceita só `hostssl` + SCRAM e rejeita TCP sem TLS; a API usa `verify-full` com a CA privada do projeto (TLS 1.3 negociado nos testes). Porta publicada apenas em `127.0.0.1`.
- Duas roles de aplicação sem superuser e sem permissão de criar objetos ou de serem donas de tabelas: `diagpro_runtime` (`NOBYPASSRLS`) para requisições de um cliente e `diagpro_platform` (`BYPASSRLS`) apenas para login, cadastro e `administrador geral`. Senhas geradas aleatoriamente por `setup_postgres_roles.py --rotate`.
- RLS forçado em 16 tabelas, sem cláusula de bypass: `SET app.bypass_rls = 'on'` não tem efeito (testado no banco real).
- Troca de `tenant_id` sem recifrar a linha é bloqueada por gatilho no banco (testado no banco real e na suíte).

**Administrador geral e cliente em gestão**
- Sem cliente escolhido (visão global), as requisições do `administrador geral` usam a role de plataforma: clientes, usuários de todos os clientes e eventos de todos os clientes.
- Com um cliente escolhido no topo da tela, o frontend envia `X-Tenant-Id`; o servidor valida que o cliente existe (senão 400) e executa a requisição com a role de runtime sob o RLS desse cliente, exatamente como um usuário dele. Nada de outro cliente aparece nem pode ser gravado.
- O cabeçalho só é considerado para usuários que são `administrador geral` no banco; para os demais é ignorado (testado). A gestão de clientes (`/admin/clients`) é sempre global.

**Cifra de campos** (`field_crypto.py`)
- AES-256-GCM com chave por cliente derivada (HKDF-SHA256) de uma chave mestra que fica fora do projeto e do banco. O AAD amarra cada valor a tabela, coluna, cliente e versão da chave: um valor copiado para outro lugar falha na autenticação.
- Sessões de runtime não decifram linhas de outro cliente, mesmo que uma injeção de SQL troque o contexto de RLS (testado).
- O tipo `Ciphertext` recusa gravar ou comparar texto claro em coluna cifrada fora do ORM.
- A antiga `FERNET_KEY` (exposta antes das correções) foi aposentada; a API não a lê mais.

**Arquivos** (`secure_files.py`)
- Arquivos cifrados por cliente em `storage_data/files` (blocos AES-256-GCM, nomes opacos); templates em `templates_eventos/*.enc`.
- Entrega por URL assinada (HMAC, 5 min, `DIAGPRO_FILE_URL_TTL`); assinatura inválida, link expirado ou escopo de outro cliente → 404. Respostas com `no-store`, `nosniff` e CSP restritiva.
- Uploads validados por extensão, tamanho e assinatura de conteúdo (HTML/SVG disfarçado de imagem é recusado).
- Caminhos enviados pelo cliente (importação DOCX, capas, timbre, avatar) só são aceitos como referência válida do próprio cliente; antes, permitiam ler arquivos arbitrários do servidor pelo gerador.

**Prova pronta e gabarito: senha do evento**
- Sorteios da prova com semente secreta por montagem (`metadados_prova.semente_gabarito`, cifrada): exportações da mesma montagem são idênticas; o gabarito não é derivável do número de questões (antes era igual em todas as provas de mesmo tamanho).
- Cada exportação de provas ou gabaritos é registrada em `audit_log_geracao` (usuário, IP, opções, cargos e SHA-256 de cada arquivo; nunca a senha). Se o registro falhar, a exportação é recusada. A aba Auditoria em Configurações lista esses registros.
- Gerar/baixar prova, ver gabarito na tela e exportar gabaritos exigem a senha do evento no cabeçalho `X-Senha-Evento` (o lote recebe no corpo); nunca na URL. Comparação em tempo constante; 5 erros em 10 min bloqueiam o usuário naquele evento (`security.evento_com_senha`). O ZIP é cifrado (AES) com a mesma senha.
- O gerador recusa (409) qualquer texto ainda em formato cifrado (`security.exigir_texto_claro`) e provas sem questões, em vez de imprimir lixo ou falhar com 500.

**Saídas e logs**
- Nenhuma prova gerada é armazenada; a pasta temporária da requisição é apagada ao final.
- `log_redaction.py` mascara `senha=`, `sig=`, tokens `Bearer`, caminhos e nomes de arquivo em todos os logs, inclusive no log de acesso do uvicorn (testado com servidor real). Logs de depuração ficam desligados por padrão.

**Configurações** (`configuracoes.py`, tabela `configuracoes` cifrada e com RLS)
- Plataforma (só admin geral, visão global): política de senha e sessão para todas as bancas, com limites seguros (ex.: senha mínima de 8 a 64).
- Banca (administrador do cliente): sessão mais curta que a da plataforma (nunca mais longa), instruções impressas por bloco/disciplina e da discursiva (padrão = textos anteriores, prova idêntica enquanto não editar), tipos de questão usados e revisão obrigatória para exportar (vira bloqueio na checagem).
- Pessoal (`/minha-conta`, qualquer perfil): trocar a própria senha (senha atual + código do autenticador) e gerar novos códigos de recuperação.

**Assistente de IA** (`assistente_ia.py`, `routes/ia.py`, tabela `uso_ia` cifrada e com RLS)
- Desligado por padrão. Só funciona se o admin geral ligar na plataforma **e** o administrador da banca ligar na banca; a banca escolhe os recursos e escreve orientações de estilo que vão em todo pedido.
- A IA recebe só o texto que o usuário mandou naquele clique: nada é lido do banco para a IA (nem prova montada, nem gabaritos de outras questões, nem nomes). HTML vira texto puro e imagens/base64 são removidas antes de sair.
- O texto enviado e o recebido nunca são gravados nem registrados em log. `uso_ia` guarda só usuário, data, tokens, sucesso e (cifrados) recurso, provedor, modelo e erro; a banca vê o resumo em Configurações > IA da banca.
- Respostas sempre em JSON com formato fixo e chegam como rascunho: o usuário escolhe o que aplicar e revisa antes de salvar. O conteúdo do usuário vai marcado como material, não como instrução.
- Limites: por usuário/dia (a banca pode reduzir), por banca/dia e 20 pedidos por minuto. Diagramador não usa.

**Avisos e e-mail** (`notificacoes.py`, `routes/notificacoes.py`, tabela `notificacoes` cifrada e com RLS)
- Todo aviso aparece no sino do topo da tela; por e-mail, conforme as preferências da pessoa em Minha conta. Avisos de segurança (novo acesso, senha alterada, 2FA resetado) são sempre enviados.
- Avisos e e-mails nunca levam conteúdo de prova: só o que aconteceu e um link interno para o DiagPro.
- Servidor SMTP em Configurações > Plataforma > E-mail de avisos; a senha fica cifrada e nunca volta para a tela. TLS obrigatório (STARTTLS ou SSL); sem criptografia só com servidor local. Nome do remetente com quebra de linha é recusado (injeção de cabeçalho).
- Fila em segundo plano junto com a API (`DIAGPRO_FILA_EMAIL=0` desliga): 5 tentativas com espera crescente; `SKIP LOCKED` evita envio duplicado.

**Acessos (sessões)** (`sessoes.py`, tabela `sessoes` com IP/navegador cifrados e RLS)
- Cada login concluído (depois do 2FA) cria um acesso; o token leva o id (`sid`) e toda requisição confere se ele não foi encerrado. Sair encerra no servidor: um token copiado deixa de valer na hora.
- Minha conta lista os acessos ativos (navegador, sistema, IP, último uso) e encerra um ou todos os outros. O administrador desconecta alguém da banca de todos os aparelhos.
- Trocar a senha encerra os outros acessos; reset do 2FA encerra todos.
- Login de navegador/sistema/rede (/24) não usados nos últimos 90 dias gera aviso de segurança (sino + e-mail obrigatório).

**Fluxo de revisão** (`fluxo_revisao.py`, `routes/revisao.py`)
- Estados: Em elaboração → Aguardando revisão → Aprovada, ou Devolvida com ajustes / Reprovada → (corrige e reenvia).
- O professor envia pela lista de questões do conteúdo (só quem elaborou ou o professor do conteúdo); revisores da banca (ou, sem revisor, os administradores) recebem aviso. A Fila de revisão no menu mostra cada estado com evento, conteúdo, autor e recado.
- A decisão do revisor avisa quem elaborou; a tela de edição mostra a observação. O nome do revisor no histórico vem do login, não do formulário.
- Questão aprovada que é alterada volta para "Em elaboração" e precisa de nova revisão (com "revisão obrigatória" ligada, isso bloqueia a exportação até reaprovar).

**Histórico de versões e questões parecidas** (`versoes_questao.py`, `routes/versoes.py`, tabela `versoes_questao` cifrada e com RLS)
- Cada criação, edição e revisão guarda a questão completa (cifrada), com autor e motivo; na 1ª alteração de uma questão antiga, o estado anterior vira a versão 1. A tela de edição lista as versões, compara com o formulário (diferenças em destaque) e traz uma versão de volta para o formulário (vale ao salvar; imagens não são restauradas).
- Ao salvar, o enunciado é comparado com as outras questões da banca (trigramas de palavras + coeficiente de Dice, tudo no servidor, sem serviço externo); a partir de 80% a tela pede confirmação. Professor vê detalhes só das questões dele; das outras, só o aviso e o grau.

**Saúde, backups e manutenção** (`saude.py`, `backups.py`, `routes/sistema.py`; Configurações > Plataforma > Saúde e backups)
- Painel do admin geral: banco (latência, TLS, tamanho), migrações em dia, RLS forçado em todas as tabelas com banca, fila de e-mails, último backup, chaves presentes, disco, LibreOffice, e-mail, IA e manutenção.
- Backup automático diário (hora e quantos guardar configuráveis; padrão 2h, 14), além do botão "Fazer backup agora": `pg_dump` direto para a cifra (nada em claro no disco), conferido logo depois (decifra inteiro e confere a assinatura `PGDMP`). Falha avisa o admin geral. Sem download pela web. Variáveis: `DIAGPRO_BACKUP_CMD` (padrão `docker exec diagpro_postgres pg_dump -U diagpro_admin -Fc diagpro`), `DIAGPRO_BACKUP_DIR`, `DIAGPRO_BACKUP_AGENDADO=0` desliga o agendador.
- Modo manutenção: todos recebem 503 com a mensagem configurada (faixa no topo de todas as telas, inclusive o login), menos o admin geral; login e `/status/manutencao` continuam abertos.

**LGPD** (`lgpd.py`, `routes/lgpd.py`, tabela `registros_lgpd` cifrada e com RLS)
- Termos de uso e política de privacidade com versão (Configurações > Plataforma > Privacidade), públicos em `/termos` e `/privacidade`. Mudou a versão, todos aceitam de novo no próximo acesso; o aceite (versão, data, IP) fica no usuário (cifrado).
- Minha conta > "Baixar meus dados": JSON com perfil, acessos, avisos, uso da IA e códigos das questões elaboradas; nunca hash de senha, segredo do 2FA ou códigos de recuperação.
- Anonimização (Usuários e contas > Anonimizar, confirmação digitando o usuário): apaga nome, e-mail, CPF, telefone, endereço, dados bancários e segredos, desativa a conta e apaga acessos e avisos; as questões continuam da banca. Ninguém anonimiza a si mesmo; administrador de banca só os da própria banca.
- Retenção configurável: avisos (180 dias), acessos/IP (90) e uso da IA (365) apagados automaticamente.
- Registros de LGPD por banca (Configurações > Banca): exportações, anonimizações, aceites e limpezas.

**Entrega segura e marca d'água** (`entregas.py`, `routes/entregas.py`, tabela `entregas` com RLS; `MarcaDagua.tsx`)
- Exportação > "Entregar por link": gera o mesmo pacote (protegido pela senha do evento) e guarda cifrado; devolve um link `/entrega/<id>` e um código de acesso de 12 caracteres, mostrado uma única vez e guardado só como hash. Validade de 1 a 72 h, 1 a 5 downloads, revogável; 5 códigos errados bloqueiam o link. Ao vencer, esgotar ou ser revogado, o arquivo é apagado (limpeza a cada 10 min). Cada download registra data e IP e avisa quem criou. Pacote com gabarito marcado não pode ser entregue por link.
- Pré-visualização da prova montada e tela de gabarito com marca d'água pessoal (usuário, data/hora, "CONFIDENCIAL"), sem seleção/cópia nem impressão pelo navegador. Os arquivos exportados não levam marca.

**Painel da banca e estatísticas pós-prova** (`estatisticas.py`, `routes/estatisticas.py`, tabela `analises_prova` cifrada e com RLS)
- Painel da banca (menu, administradores): eventos com elaboração x meta, cargos e provas montadas, questões por estado de revisão e por tipo, fila de revisão, exportações e uso da IA em 30 dias, entregas ativas e equipe. Só números.
- Estatísticas pós-prova (menu do evento): CSV com `tipo_prova` e `respostas` (uma letra por questão na ordem do caderno de cada variação), com a senha do evento. Por questão: % de acerto, % em branco, correlação ponto-bisserial (com o total sem a própria questão), índice D (27% superior x inferior) e alertas (discriminação negativa = gabarito suspeito, acerto muito baixo/alto, muitos em branco); geral: média, desvio, mínimo, máximo e KR-20. Anuladas ficam fora. O CSV é lido só em memória (inscrição e nome ignorados); guarda-se só o resultado agregado.
- Correção: gerar o gabarito (tela, ZIP de gabaritos, estatísticas) gravava a prova em claro em `%TEMP%\dummy.docx` e não apagava; agora usa uma pasta privada apagada em seguida.

**Autenticação e HTTP**
- Política de senha (`politica_senha.py`): mínimo de 12 caracteres e 3 de 4 tipos, sem usuário/e-mail, sem senha comum ou sequência, sem repetir as 5 últimas (histórico bcrypt cifrado), validade de 180 dias. Senha definida por administrador é provisória. Troca obrigatória (provisória, vencida ou fora da política) acontece depois do 2FA e antes do acesso. Trocar a própria senha exige a senha atual e um código do autenticador.
- Sessão: token de 30 min renovado pela tela só enquanto há uso (`/auth/renovar`); 30 min sem uso encerram; limite absoluto de 12 h desde o login (`auth_time`). 401 em qualquer tela leva ao login com aviso.
- 2FA (TOTP) obrigatório para todos os usuários: o segredo do autenticador e os códigos de recuperação (HMAC) ficam cifrados; o mesmo código não vale duas vezes; 5 erros em 10 min bloqueiam; tokens sem a marca `mfa` (anteriores ao 2FA ou passes) são recusados. O administrador reseta o 2FA de outro usuário (celular perdido), nunca o próprio.
- JWT `HS256` (30 min), `bcrypt`, bloqueio de inativos, rate limits (ver [Seção 2](#2-estado-atual-das-funcionalidades)). reCAPTCHA em *fail-open* sem chave. Sem refresh token; o frontend guarda o token em `localStorage`.
- Cabeçalhos: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `X-Request-ID`, `Cache-Control: no-store` em rotas de API. HSTS com `ENABLE_HSTS=true`.

**Isolamento multi-tenant: estado verificado**
- Testado: RLS no PostgreSQL com a role de runtime (leitura e escrita cruzada bloqueadas, pool sem vazamento, bypass bloqueado), recusa de decifrar linhas de outro cliente, isolamento HTTP em eventos, usuários, biblioteca e jobs, cliente em gestão do `administrador geral` e isolamento de arquivos por cliente.
- Não testado automaticamente: isolamento entre clientes nas rotas de frases, templates, questões, textos, cargos, provas e gabaritos (protegidas por RLS + `evento_autorizado`/filtro de tenant; apenas inspecionadas na revisão atual).

**Limites conhecidos**
- Metadados não cifráveis ficam visíveis a quem acessar o banco: IDs, `tenant_id`, códigos técnicos, papéis, estados, datas, contagens e tamanho aproximado dos textos.
- Durante a geração, arquivos decifrados existem por alguns segundos na pasta temporária do usuário do serviço (LibreOffice e Java precisam deles). Apagar não sobrescreve o disco: use criptografia de disco (BitLocker) no servidor.
- `/docs` e `/openapi.json` são públicos.

---

## 15. Instalação, Variáveis de Ambiente e Execução

### Pré-requisitos
- **Python 3.11**, **Docker** (PostgreSQL 16 do `docker-compose.yml`), **LibreOffice** e **Java** (OpenJDK 17 no `Dockerfile`), **Node.js 18+** para o frontend.
- Na máquina de desenvolvimento há serviços PostgreSQL 16/17/18 instalados localmente; a referência validada é o contêiner `postgres:16-alpine` do compose (porta `5435`, só `127.0.0.1`).

### Segredos (fora do projeto)
Todos ficam em `%LOCALAPPDATA%\DiagPro\secrets` (pasta acessível apenas pelo usuário do serviço):

| Arquivo | Gerado por | Função |
| :--- | :--- | :--- |
| `master.key` | `python -m backend.app.field_crypto genkey` | Chave mestra da cifra de campos e de arquivos. **Sem ela, os dados são irrecuperáveis.** |
| `backup.key` | `python scripts/backup_crypto.py genkey` | Chave dos backups cifrados |
| `pg-tls\ca.crt`, `ca.key`, `server.crt`, `server.key` | `python scripts/gen_pg_tls.py` | CA privada e certificado TLS do PostgreSQL |
| `legacy_fernet.key` | — | Chave Fernet aposentada; necessária só para converter backups anteriores à fase 1b |

Guarde cópias **offline** de `master.key`, `backup.key` e `pg-tls\ca.key`. Nenhum desses scripts sobrescreve uma chave existente.

### Variáveis de Ambiente (`.env`)
Copie `.env.example` para `.env` e preencha. Nunca versione o `.env`.

| Variável | Obrigatória | Uso |
| :--- | :--- | :--- |
| `DATABASE_URL` | Sim | `postgresql+asyncpg://diagpro_runtime:<senha>@127.0.0.1:5435/diagpro` |
| `PLATFORM_DATABASE_URL` | Sim | `postgresql+asyncpg://diagpro_platform:<senha>@127.0.0.1:5435/diagpro` (deve ser diferente da anterior) |
| `ALEMBIC_DATABASE_URL` | Para migrações/scripts | `postgresql+psycopg2://diagpro_admin:<senha>@127.0.0.1:5435/diagpro` |
| `DB_SSLMODE`, `DB_SSL_ROOT_CERT` | Sim (padrão `verify-full`) | TLS com o banco; `disable` só no CI efêmero |
| `JWT_SECRET_KEY` (ou `SECRET_KEY`) | Sim | Assinatura JWT |
| `DIAGPRO_MASTER_KEY_FILE` | Não | Caminho da chave mestra (padrão `%LOCALAPPDATA%\DiagPro\secrets\master.key`) |
| `DIAGPRO_FILES_DIR` | Não | Armazenamento cifrado de arquivos (padrão `storage_data/files`) |
| `DIAGPRO_FILE_URL_TTL` | Não | Validade das URLs assinadas em segundos (padrão 300) |
| `DIAGPRO_LOG_LEVEL` | Não | Nível de log (padrão `WARNING`; `DEBUG` expõe detalhes de depuração) |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT` | Para o compose | Contêiner PostgreSQL |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_PLATFORM_POOL_SIZE`, `DB_PLATFORM_MAX_OVERFLOW` | Não | Pools de conexão |
| `CORS_ORIGINS`, `ENABLE_HSTS`, `RATE_LIMIT_ENABLED` | Não | HTTP e rate limit |
| `RECAPTCHA_SECRET_KEY` | **Obrigatória** | Sem ela, nenhum login é aceito (`DIAGPRO_RECAPTCHA_DESATIVADO=1` só em testes) |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | Não | Chave de IA de reserva (a salva em Configurações > Plataforma tem prioridade) |
| `BING_API_KEY` | Não | Verificação de plágio |
| `REDIS_URL`, `S3_*`, `LOCAL_STORAGE_DIR` | Não | Rate limit compartilhado e `storage.py` |

### Preparar um ambiente novo
```powershell
# 1. Dependências e chaves
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m backend.app.field_crypto genkey
.\.venv\Scripts\python.exe scripts/backup_crypto.py genkey
.\.venv\Scripts\python.exe scripts/gen_pg_tls.py

# 2. PostgreSQL 16 (somente 127.0.0.1:5435)
docker compose up -d db

# 3. TLS no servidor: instalar certificado e exigir hostssl + SCRAM
$tls = "$env:LOCALAPPDATA\DiagPro\secrets\pg-tls"
docker cp "$tls\server.crt" diagpro_postgres:/var/lib/postgresql/data/server.crt
docker cp "$tls\server.key" diagpro_postgres:/var/lib/postgresql/data/server.key
docker exec diagpro_postgres sh -c 'cd $PGDATA && chown postgres:postgres server.* && chmod 600 server.key'
#    pg_hba.conf: "local all all trust", "hostssl all all all scram-sha-256", "host all all all reject"
docker exec diagpro_postgres psql -U diagpro_admin -d diagpro -c "ALTER SYSTEM SET ssl = 'on'" -c "ALTER SYSTEM SET ssl_min_protocol_version = 'TLSv1.2'" -c "SELECT pg_reload_conf()"

# 4. Schema, RLS e roles (role administrativa em ALEMBIC_DATABASE_URL)
.\.venv\Scripts\alembic.exe upgrade head          # deve terminar em a2b4c6d8e0f1
Get-Content backend/app/rls_policies.sql -Raw | docker exec -i diagpro_postgres psql -U diagpro_admin -d diagpro
.\.venv\Scripts\python.exe scripts/setup_postgres_roles.py --rotate   # cria as roles e grava as senhas no .env

# 5. API (a partir da raiz do projeto)
.\.venv\Scripts\uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8000
```
API em `http://127.0.0.1:8000`, Swagger em `/docs` e saúde em `/health`. **Não use `alembic stamp head`** em banco vazio (não cria tabelas) e não gere uma nova revisão inicial.

Frontend (`frontend/src/`; em 19/11/2026 o servidor de desenvolvimento compilou e `npx tsc --noEmit` passou sem erros):
```powershell
cd frontend; npm install; npm start   # http://localhost:3000; a API é http://127.0.0.1:8000 (frontend/src/api.ts)
```

### Backup e restauração
```powershell
$bk = "$env:LOCALAPPDATA\DiagPro\backups\pg_diagpro_$(Get-Date -f yyyyMMdd-HHmmss).dump.enc"
docker exec diagpro_postgres pg_dump -U diagpro_admin -d diagpro -Fc | .\.venv\Scripts\python.exe scripts/backup_crypto.py encrypt $bk
# verificar:   .\.venv\Scripts\python.exe scripts/backup_crypto.py decrypt $bk | docker exec -i diagpro_postgres pg_restore --list
# restaurar:   ... decrypt $bk | docker exec -i diagpro_postgres pg_restore -U diagpro_admin -d <banco_vazio> --no-owner --role=diagpro_admin
```
O dump já contém os campos cifrados; os arquivos de `storage_data/` e `templates_eventos/` também são cifrados e devem ser copiados junto. Restaurar exige a mesma `master.key`.

---

## 16. Testes e Validação

### Suíte automatizada (`tests/test_security_rbac_rls.py`, `tests/test_assistente_ia.py` , `tests/test_notificacoes.py`, `tests/test_sessoes.py`, `tests/test_revisao.py`, `tests/test_versoes.py`, `tests/test_sistema.py`, `tests/test_lgpd.py`, `tests/test_entregas.py` e `tests/test_estatisticas.py`, 45 testes)

Execute com `.\.venv\Scripts\python.exe scripts/run_tests.py` (contêiner `diagpro_postgres` no ar). O script recria o banco descartável `diagpro_test`, aplica migrações, RLS e roles, gera uma chave mestra de teste temporária e apaga tudo ao final; o banco real e a chave real não são tocados.

| Área | Testes |
| :--- | :--- |
| Autenticação e RBAC | `test_two_factor_is_mandatory_for_everyone`, `test_password_policy_rules`, `test_forced_password_change_session_renewal_and_recaptcha`, `test_platform_and_bank_settings_take_effect`, `test_unauthenticated_endpoints_return_401`, `test_public_register_blocks_admin_escalation_and_bad_uploads`, `test_rbac_matrix_five_roles` |
| Isolamento e RLS | `test_http_tenant_isolation_between_tenant_1_and_tenant_2`, `test_postgres_rls_isolation_and_pool_non_leakage`, `test_runtime_role_cannot_bypass_rls_via_session_variable`, `test_health_request_id_and_biblioteca_tenant_isolation`, `test_storage_path_traversal_and_export_jobs_tenant_isolation` |
| Cifra de campos | `test_field_crypto_roundtrip_binding_and_blind_index`, `test_database_stores_only_ciphertext_and_orm_returns_plaintext`, `test_plaintext_write_to_encrypted_column_is_blocked`, `test_runtime_session_refuses_rows_of_other_tenant_even_with_tampered_context` |
| Arquivos | `test_secure_files_store_sign_and_isolation`, `test_upload_returns_signed_url_and_public_folders_are_gone` |
| Gestão multi-cliente | `test_tenant_change_without_reencryption_is_blocked_by_database`, `test_admin_geral_must_choose_valid_tenant_to_create_event`, `test_admin_geral_global_view_and_managed_client_isolation` |
| Questões e conteúdos | `test_question_types_create_edit_review_and_professor_contents` |
| Prova pronta e gabarito | `test_finished_exam_and_answer_key_require_event_password`, `test_generator_refuses_ciphertext`, `test_cors_preflight_allows_app_custom_headers`, `test_exam_seed_is_secret_reproducible_and_legacy_compatible`, `test_export_preferences_and_precheck_endpoints`, `test_generator_renders_editor_html_inline_and_answer_lines` |
| Assistente de IA | `test_ai_assistant_rules_secrecy_and_limits`, `test_ai_text_is_stripped_of_html_and_images` (provedor falso; nunca chama IA real) |
| Avisos e e-mail | `test_notifications_queue_preferences_and_isolation` (SMTP falso; nunca envia e-mail real) |
| Acessos | `test_sessions_logout_remote_signout_and_new_device_alert`, `test_browser_summary` |
| Fluxo de revisão | `test_review_workflow_send_queue_return_approve_reopen` |
| Versões e parecidas | `test_question_versions_and_similar_questions` |
| Backups, saúde e manutenção | `test_backup_retention_health_and_maintenance` (dump sintético; nunca o banco real) |
| LGPD | `test_lgpd_terms_export_anonymize_records_and_retention` |
| Entrega segura | `test_secure_delivery_link_code_limits_expiry_and_revocation`, `test_delivery_code_format` |
| Estatísticas e painel | `test_item_analysis_flags_wrong_key_easy_item_and_ignores_annulled`, `test_csv_reading_ignores_personal_columns_and_validates`, `test_analysis_endpoint_rules_and_bank_dashboard` |
| HTTP, saídas e logs | `test_security_headers_and_rate_limiting`, `test_log_redaction_masks_secrets_paths_and_exam_file_names`, `test_debug_and_disk_persisting_export_routes_were_removed` |

Os testes rodam contra PostgreSQL com a role de runtime, dados sintéticos (`conftest.py`) e uma chave mestra de teste. Nunca use o banco real nem a chave real nos testes.

### Verificações executadas (19/11/2026, Windows, `.venv` da raiz)
- **Suíte:** 31 aprovados num banco descartável `diagpro_test` (PostgreSQL 16, TLS `verify-full`, role `diagpro_runtime`).
- **Migração `a9d4c2e6f0b1` no banco real**, precedida de backup cifrado: 16 gatilhos e 4 restrições únicas por cliente criados; `UPDATE` direto de `tenant_id` recusado.
- **Migração `c5e8f1a3b9d2` no banco real**, precedida de backup cifrado verificado: coluna `imagem_path_item` criada e incluída na trava de troca de tenant.
- **Prova mista no banco de teste** (múltipla escolha + Certo/Errado com imagem + Subjetiva de 7 linhas): numeração 1..7 sem saltos, comando sem número, itens em sequência, 7 linhas, gabarito C/E nos números certos, versão marcada com (C)/(E), sem tags HTML, exportações idênticas.
- **Diagramação ponta a ponta no banco de teste** (dados sintéticos): 33 verificações (checagem e bloqueio, 3 exportações idênticas, gabarito igual à ordem impressa, montagens diferentes com gabaritos diferentes, prova antiga inalterada, nomes, gabarito marcado com aviso e cores, relatório, padrão do evento, auditoria) e 10 verificações de "Atualizar questões" (só a questão editada muda; ordem e gabarito mantidos).
- **Migração `d8b2f4a6c1e3` no banco real**, após backup cifrado verificado. Checagem nas provas reais: cargo 203 bloqueado — questão 15 (Q-0005) com as 5 alternativas de imagem sem o caminho na cópia da montagem (corrigível com "Atualizar questões").
- **Reparo de Fernet legado embutido no banco real** (`repair_nested_legacy_fernet.py`), após simulação e backup cifrado verificado: 433 valores recuperados em 2 provas montadas e 2 questões discursivas, nenhuma falha; varredura posterior sem tokens antigos e colunas ainda cifradas (`e1.`).
- **Geração de prova ponta a ponta** no banco de teste: ver linha "Montagem, Simulação e Geração" na [Seção 2](#2-estado-atual-das-funcionalidades); na API real, gabarito e download recusados sem a senha (403).
- **Conteúdos e questões:** 46 verificações de gravação via API num banco de teste com dados sintéticos (4 tipos de questão, revisão, textos, conteúdos); no banco real, todas as telas de conteúdos/questões/textos abertas e todos os editores "Editar" acionados em navegador automatizado, sem salvar, sem erros.
- **API real (19/11):** visão global do `administrador geral` (usuários de todos os clientes), cliente em gestão restrito ao cliente escolhido, cliente inexistente recusado, pré-voo CORS com `X-Tenant-Id` aceito; chamadas de leitura de todas as telas do evento (montagem, geração, exportação, templates, gabaritos, questões, revisões e textos) com 200 nos 3 eventos existentes.

Verificações de 18/11/2026:
- **Teste de fumaça da API** no mesmo banco: 34 chamadas (empresa, eventos, cargos, frases com importação, conteúdos, ciclo completo de questão, textos, usuários, clientes, auditoria) e checagem de uploads de imagem; varredura sem texto claro nas colunas cifradas.
- **Migrações no banco real**, cada uma ensaiada antes numa cópia restaurada de backup:
  - RLS sem bypass;
  - recifragem de 4.034 valores (1.269 linhas; 607 camadas Fernet antigas removidas), com cada valor decifrado e comparado;
  - 14 arquivos e 2 templates movidos para o armazenamento cifrado, conferidos por SHA-256.
- **Banco real após as migrações:** carga completa pelo ORM (por cliente na role de runtime e pela de plataforma), login pelo índice cego, leituras pela API e varredura de texto claro (nenhum).
- **Geração real numa cópia do banco:**
  - PDF com capa via Java;
  - lote do frontend com ZIP AES que não abre sem senha;
  - ZIP de gabaritos;
  - nenhum arquivo nem pasta temporária remanescente e nenhum conteúdo de prova nos logs.
- **Log de acesso do uvicorn** (servidor real): senha, assinatura e token não aparecem.
- **TLS:** conexão sem TLS recusada, CA errada recusada, `verify-full` aceito.
- **Backups:** cifrados, verificados com `pg_restore --list` e restaurados com sucesso em bancos de ensaio.

### Não executado
- Workflow de CI no GitHub Actions.
- reCAPTCHA junto ao Google e chamadas OpenAI/Bing/Dicio.
- Build da imagem Docker da API.
- Build de produção e testes automatizados do frontend; fluxos que gravam dados (montar, gerar, exportar, revisar) pela interface.
- Extração DOCX automatizada e regras de embaralhamento/variação.

---

## 17. Limitações Conhecidas e Roadmap Técnico

### Limitações Atuais
- **Histórico do Git:** o banco SQLite antigo (com dados pessoais) e as imagens de prova que estavam em `static/` continuam no histórico de commits anteriores. Removê-los exige reescrever o histórico (autorização do responsável).
- **Frontend:** a tela de cadastro de disciplinas chama `POST /disciplinas/`, que não existe no backend (rota não registrada); `EditarProvaPage` é um esqueleto vazio. Vários arquivos de `frontend/src/` têm finais de linha `\r\r\n`; edite preservando o formato ou normalize num commit próprio.
- **Bugs conhecidos:** frase duplicada devolve 500 em vez de 400; Chat IA inoperante (SDK `openai` v1).
- **Diagramação:** itens de Certo/Errado saem na ordem cadastrada (não são embaralhados entre variações); Discursiva só é impressa em bloco cujo nome contém "Discursiva" (a checagem avisa); a geração roda dentro da requisição (lotes grandes podem demorar; a API fica ocupada durante a conversão para PDF).
- **Chamadas legadas sem efeito:** `encrypt_text`/`decrypt_text`/`encrypt_pii` ainda aparecem nas rotas, mas não fazem nada (a cifra é feita no ORM).
- **Rotação de chave:** o formato dos valores cifrados guarda a versão da chave, mas não há script de rotação.
- **Busca da biblioteca:** decifra as questões do cliente na memória; mais lenta em volumes grandes.
- **Arquivos órfãos:** imagens de pré-visualizações de importação não confirmadas ficam cifradas no armazenamento sem limpeza automática.
- **Dependências:** `redis` sem versão fixada; `boto3` ausente; imagem `minio/minio:latest` sem versão fixada.
- Token em `localStorage` (sessão curta e renovada só com uso), `/docs` público.

### Próximos Passos Prioritários
1. **Limpar o histórico do Git** (banco antigo e imagens de prova).
2. **Testes de isolamento** em todas as rotas de questões, textos, cargos, provas e gabaritos; executar o CI no GitHub.
3. **Corrigir os bugs conhecidos**.
4. **Rotação de chaves** (mestra e roles) com script e procedimento documentado; avaliar KMS para a chave mestra.
5. **Endurecimento de sessão:** token em cookie `HttpOnly`/`SameSite`, `/docs` restrito.

---

## 18. Diretrizes para Desenvolvimento e Contribuição

- **Fonte da verdade:** código-fonte, modelos, rotas e migrações atuais prevalecem sobre documentos antigos.
- **Isolamento multi-tenant:** nunca confiar em `tenant_id` enviado pelo cliente; derivar sempre do usuário autenticado e validar pertencimento ao evento/recurso. Use `get_tenant_db`; a role de plataforma é só para login, cadastro e `administrador geral` na visão global. Para o `administrador geral`, use `current_user.tenant_id` (o cliente em gestão) e nunca atribua um cliente padrão.
- **Dados sensíveis:** toda nova coluna de texto/JSON com conteúdo de prova, dado pessoal ou dado de cliente deve entrar em `field_crypto.ENCRYPTED` e ser declarada como `Ciphertext`. Buscas exatas em colunas cifradas usam `blind_eq` (índice cego); `LIKE`/ordenação nelas não funcionam.
- **Arquivos:** nunca gravar em pastas públicas nem abrir caminhos vindos do cliente. Use `secure_files.save_upload_http` para uploads, `ref_from_client`/`sanitize_client_paths` para valores devolvidos pelo cliente e `materialize_into` com `request_workdir` para o gerador.
- **Saídas:** provas e gabaritos gerados são entregues em memória e nunca persistidos.
- **Logs:** não usar `print` para dados operacionais; não registrar senhas, tokens, chaves, conteúdo de prova ou dados pessoais.
- **Segurança por padrão:** toda nova rota exige autenticação, `require_roles` e testes negativos (sem token, perfil errado, outro cliente) em `tests/`.
- **Migrações:** novas revisões Alembic encadeadas à atual, revisadas manualmente, ensaiadas numa cópia do banco e precedidas de backup cifrado; nunca editar revisões já aplicadas.
- **Segredos:** nunca registrar senhas, chaves (`master.key`, `JWT_SECRET_KEY`), tokens ou dados pessoais em código, logs ou commits.
