# DiagPro

**Sistema de gestão de bancas organizadoras, concursos públicos, questões, provas e gabaritos.**

O **DiagPro** é uma plataforma multi-tenant voltada à gestão de concursos públicos e avaliações, cobrindo desde a administração das bancas organizadoras (clientes) e estruturação dos eventos/editais até a elaboração, importação, revisão, montagem e geração automatizada de provas, capas em PDF e gabaritos.

> **Nota de transparência técnica:** Este documento reflete exclusivamente o que foi verificado diretamente no código-fonte e nos arquivos de configuração atuais do repositório. Itens estruturados ou pendentes de validação em execução estão explicitamente sinalizados.

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

- Administrar múltiplos clientes/bancas (**multi-tenancy lógico** via `tenant_id`, com base estruturada para PostgreSQL + Row-Level Security).
- Estruturar concursos (**Eventos**), **Cargos**, **Disciplinas** e **Conteúdos Programáticos** com metas por professor.
- Manter um **Banco de Questões** (múltipla escolha, certo/errado, discursiva e subjetiva) com textos de referência, imagens e trilha de revisão.
- Automatizar a **importação de questões via DOCX**, montagem de cadernos, simulações, geração de variações e exportação de **DOCX, PDF, capas AcroForm e pacotes ZIP**.
- Registrar auditoria de geração de provas (`audit_log_geracao`).

---

## 2. Estado Atual das Funcionalidades

Classificação adotada nesta auditoria:
- **Implementada e verificada:** comportamento presente no código e validado por compilação/inspeção direta.
- **Implementada parcialmente:** existe implementação no código, porém com lacunas, mocks ou pendências.
- **Estruturada, mas não validada:** modelos, scripts ou configurações existem no repositório, mas não foram executados/validados em runtime.
- **Planejada:** descrita em roadmap/relatório, sem implementação no código atual.
- **Não identificada:** sem evidência suficiente no repositório atual.

| Funcionalidade | Classificação | Evidência / Observação no Código |
| :--- | :--- | :--- |
| Autenticação JWT (`HS256`) + `bcrypt` + reCAPTCHA | **Implementada parcialmente** | `backend/app/auth.py`, `backend/app/routes/auth.py` (código inspecionado e validado por `py_compile`; fluxo E2E de `/auth/login` e reCAPTCHA não testado em execução nesta auditoria) |
| Gestão de Tenants e Dashboard (`admin_geral`) | **Implementada parcialmente** | `backend/app/admin_clients.py` (sem testes automatizados de isolamento) |
| Gestão de Usuários e Cadastro Público | **Implementada parcialmente** | `backend/app/routes/users.py` (cadastro público bloqueado para roles admin; nasce inativo) |
| CRUD de Eventos, Cargos, Disciplinas e Conteúdos | **Implementada parcialmente** | `eventos.py`, `cargos.py`, `cargos_import.py`, `conteudos.py` (nem todas as rotas usam `evento_autorizado` / RBAC estrito) |
| Banco de Questões, Textos de Referência e Revisão | **Implementada parcialmente** | `questoes.py`, `textos_referencia.py`, `utils_vinculo.py` |
| Importação de Questões via DOCX | **Implementada parcialmente** | `questoes.py`, `core/docx_parser.py` (`backend/app/importador.py` existe no repo, mas não está registrado em `main.py`) |
| Montagem, Simulação e Geração de Provas/Gabaritos | **Implementada parcialmente** | `provas.py`, `provas_geracao.py`, `gabarito.py`, `core/document_generator.py` |
| Exportação DOCX, PDF (LibreOffice), Capas PDFBox e ZIP | **Implementada parcialmente** | `exportacao.py`, `PreencheCapaPDF_JSON_PDFBox.java` (execução síncrona na requisição HTTP) |
| Auditoria de Geração (`audit_log_geracao`) | **Implementada parcialmente** | `backend/app/routes/audit_log.py` (cobre geração, não cobre leitura/edição geral) |
| Chat com IA (OpenAI `gpt-3.5-turbo`) e Plágio (Bing) | **Implementada parcialmente** | `ia_chat.py`, `plagio.py` (autenticados, sem rate limiting) |
| Dicionário (`dicio.com.br`) | **Implementada parcialmente** | `dicionario.py` (dependente de scraping HTML via regex) |
| Biblioteca de Questões (`/api/biblioteca`) | **Implementada parcialmente** | `biblioteca.py` retorna dados mockados (`QUESTOES_FAKE`) |
| PostgreSQL Multi-Tenant com RLS e Alembic | **Estruturada, mas não validada** | `database.py`, `db_models.py`, `rls_policies.sql`, `docker-compose.yml`, `alembic/`, `scripts/migrate_sqlite_to_postgres.py` (ainda não executado contra Postgres ativo) |
| Frontend Web (código-fonte React/TS) | **Implementada parcialmente** | `frontend/build/` e `frontend/package.json` presentes; `frontend/src/` e `frontend/public/` ausentes no repo local |
| Suíte de Testes Automatizados | **Não identificada** | Apenas `backend/app/test_upload.py` (snippet de 7 linhas); não há pasta/suíte `pytest` |
| Filas Assíncronas (Redis/Celery/ARQ), Object Storage (S3/MinIO) e CI/CD | **Planejada** | Previsto no roadmap técnico; não implementado no código |

---

## 3. Fluxo Operacional do Sistema

1. **Cadastro do Cliente (`Tenant`)**: O `administrador geral` registra a banca organizadora (`/admin/clients`) e cria o usuário `administrador` do tenant.
2. **Equipe e Permissões**: O `administrador` do tenant cadastra usuários internos ou aprova cadastros externos (`/users/register`) de `professor`, `revisor` e `diagramador`.
3. **Estruturação do Evento**: Criação do concurso/edital (`/eventos`), cadastro manual ou via CSV de cargos (`/cargos`, `/cargos/import-csv`), upload de capas PDF e cadastro de conteúdos programáticos (`/conteudos`, `/conteudos/csv`) vinculados a professores.
4. **Elaboração e Revisão**: Professores criam ou importam questões (`.docx`) e textos de referência; revisores analisam e registram pareceres em `HistoricoRevisaoQuestao`.
5. **Montagem e Simulação**: Diagramadores/administradores montam a prova por cargo (`/provas`), definem variações e embaralhamento (`/provas/definir-geracao`) e simulam frases/itens Certo-Errado.
6. **Geração e Exportação**: Após validação da senha do evento (`/api/export/eventos/{evento_id}/validar-senha`), o sistema gera os cadernos DOCX/PDF, preenche capas PDF via Java PDFBox, gera gabaritos e empacota em ZIP, gravando log em `audit_log_geracao`.

---

## 4. Perfis de Acesso e Responsabilidades (RBAC)

Definidos em `backend/app/roles.py` (`UserRole`):

| Perfil (`UserRole`) | Escopo | Responsabilidades Previstas |
| :--- | :--- | :--- |
| `administrador geral` | Global (todos os tenants) | Gerenciar clientes/tenants (`/admin/clients`), dashboard consolidado e criação de administradores por tenant. |
| `administrador` | Tenant | Gerenciar usuários do seu cliente, dados da empresa (`company_data`), eventos, cargos e configurações. |
| `professor` | Tenant | Elaborar e editar questões, textos de referência e gerenciar seus conteúdos atribuídos (`/conteudos/meus`). |
| `revisor` | Tenant | Revisar questões submetidas e registrar histórico de aprovação/observações (`HistoricoRevisaoQuestao`). |
| `diagramador` | Tenant | Gerenciar templates, montar provas, simular variações e gerar/exportar arquivos finais e gabaritos. |

---

## 5. Arquitetura Técnica

O projeto encontra-se em transição entre uma aplicação desktop Python legada (`core/` com `customtkinter`/`tkinter`) e uma arquitetura Web Full-Stack (`backend/` + `frontend/`), compartilhando o motor de geração e parsing de documentos:

```text
+-------------------------------------------------------+
|              FRONTEND (React 18 / TS / MUI)           |
|   Artefato compilado em frontend/build/               |
|   (código-fonte frontend/src/ ausente no repo local)  |
+---------------------------+---------------------------+
                            | HTTP / REST (JSON + Form)
+---------------------------v---------------------------+
|             BACKEND API (FastAPI / Uvicorn)           |
|  - Rotas REST (backend/app/routes/, admin_clients.py) |
|  - Auth JWT + bcrypt (auth.py) + Helpers (security.py)|
|  - Criptografia Fernet (utils_crypto.py)              |
+-------------+---------------------------+-------------+
              |                           |
              v                           v
+---------------------------+  +------------------------+
|  Núcleo Core (core/)      |  |  Motor PDFBox (Java)   |
|  - DocumentGenerator      |  |  PreencheCapaPDF_JSON  |
|  - DocxParser             |  |  pdfbox-app-3.0.5.jar  |
|  - LibreOffice (PDF)      |  +------------------------+
+-------------+-------------+
              | SQLAlchemy Async
+-------------v-----------------------------------------+
|   BANCO DE DADOS                                      |
|   - Atual em uso: SQLite WAL (diagprooff.db)          |
|   - Estruturado para migração: PostgreSQL 16 + RLS    |
+-------------------------------------------------------+
```

---

## 6. Tecnologias e Dependências Identificadas

- **Backend Python**: FastAPI, Uvicorn (`0.37.0` verificado no `.venv`), SQLAlchemy Async (`aiosqlite` para SQLite; `asyncpg` e `psycopg2-binary` instalados para PostgreSQL), Alembic (`1.20.1`), Pydantic, `python-jose`, `passlib` (`bcrypt`), `cryptography` (`Fernet`), `python-docx`, `pypdf`, `pyzipper`, `openai`, `requests`, `python-dotenv`.
  - *Observação:* `backend/requirements.txt` lista apenas 5 pacotes (`fastapi`, `uvicorn`, `openai`, `requests`, `python-dotenv`) e está desatualizado em relação ao ambiente real.
- **Processamento de Documentos Externo**: LibreOffice (`soffice.exe` para conversão DOCX → PDF) e Java + **Apache PDFBox 3.0.5** (`backend/app/pdfbox-app-3.0.5.jar`, `json.jar`).
- **Frontend (`frontend/package.json`)**: React `18.2.0`, TypeScript `4.9.5`, Material UI v7 (`@mui/material`, `@mui/icons-material`, `@mui/x-date-pickers`), TipTap v3 (`@tiptap/react` + extensões de tabela, matemática/KaTeX, imagem, colaboração `yjs`), `@dnd-kit`, `axios`, `react-router-dom` v7, `html2pdf.js`, `react-markdown`, `react-google-recaptcha`.
- **Infraestrutura**: Docker (`docker-compose.yml` com `postgres:16-alpine`).

---

## 7. Estrutura de Diretórios Real

```text
DiagPro/
├── alembic/                      # Ambiente e template de migrações Alembic
├── alembic.ini                   # Configuração do Alembic (lê DATABASE_URL do .env)
├── backend/
│   ├── app/
│   │   ├── routes/               # Routers FastAPI por domínio (20 arquivos)
│   │   ├── admin_clients.py      # Rotas de gestão multi-tenant (admin geral)
│   │   ├── auth.py               # JWT, bcrypt, get_current_user, get_admin_user
│   │   ├── campos_capa.py        # Mapeamento de ~40 campos para capa PDF
│   │   ├── database.py           # Engine SQLAlchemy Async + set_tenant_context (RLS)
│   │   ├── db_models.py          # 17 modelos ORM unificados em Base.metadata
│   │   ├── html_to_docx.py       # Conversor HTML -> python-docx
│   │   ├── importador.py         # Rota auxiliar de importação DOCX
│   │   ├── main.py               # Aplicação FastAPI e registro de rotas
│   │   ├── models.py             # Schemas Pydantic
│   │   ├── PreencheCapaPDF_JSON_PDFBox.java  # Preenchedor AcroForm PDFBox 3.0.5
│   │   ├── rls_policies.sql      # Políticas RLS PostgreSQL para 16 tabelas
│   │   ├── roles.py              # Enum UserRole (5 perfis)
│   │   ├── security.py           # Helpers evento_autorizado e path traversal
│   │   ├── utils_codigo_curto.py # Gerador de códigos curtos únicos por tenant
│   │   ├── utils_crypto.py       # Criptografia simétrica Fernet
│   │   └── utils_vinculo.py      # Sincronização texto de referência <-> questão
│   └── requirements.txt          # Lista parcial de dependências Python
├── core/                         # Núcleo legado desktop + motor de docs/parser
│   ├── app_controller.py         # Controlador legado (customtkinter/tkinter)
│   ├── document_generator.py     # DocxProofGenerator, PdfConverter, ArchiveManager, AnswerKeyGenerator
│   ├── docx_parser.py            # Parser de questões/tabelas em DOCX
│   ├── elements.py               # Modelos internos/Pydantic do core
│   ├── event_manager.py          # Gestão legada de eventos
│   └── utils.py                  # Helpers gerais (datas, gabarito, sanitização)
├── frontend/
│   ├── build/                    # Build estático compilado do frontend
│   ├── package.json              # Dependências React/TS/MUI/TipTap
│   └── (src/ e public/ ausentes no repositório local)
├── scripts/
│   └── migrate_sqlite_to_postgres.py  # Migração de dados SQLite -> PostgreSQL
├── docker-compose.yml            # Serviço PostgreSQL 16-alpine
├── diagprooff.db                 # Banco SQLite local em modo WAL
├── create_db.py                  # Script legado de criação do banco
└── update_password.py            # Utilitário pontual para senha de evento
```

---

## 8. Modelo de Dados

Definido em `backend/app/db_models.py` (**17 tabelas** registradas em `Base.metadata`):

- **Multi-tenancy e Acesso (1 tabela global + 2 com `tenant_id`):**
  - `tenants` (`Tenant`) — tabela raiz de clientes/bancas (não possui `tenant_id`, pois define os próprios tenants; por isso não recebe política RLS de `tenant_id` em `rls_policies.sql`).
  - `users` (`User`, com `tenant_id` nullable para `administrador geral`, dados cadastrais, especialidade e dados bancários/PIX), `company_data` (`Company`).
- **Estrutura de Concursos:** `Eventos` (`Evento`, com soft delete e `senha_evento_cripto`), `Cargos` (`Cargo`, com timbre e capas PDF), `Disciplinas` (`Disciplina`), `DisciplinasDaProva` (`DisciplinaDaProva`), `conteudos` (`Conteudo`).
- **Questões e Apoio:** `TextosReferenciaGeral` (`TextoReferenciaGeral`), `QuestoesBanco` (`QuestoesBanco`), `OpcoesQuestao` (`OpcoesQuestao`), `ItensVerdadeiroFalso` (`ItensVerdadeiroFalso`), `DetalhesQuestaoDiscursiva` (`DetalhesQuestaoDiscursiva`), `HistoricoRevisaoQuestao` (`HistoricoRevisaoQuestao`).
- **Provas e Auditoria:** `ProvasMontadas` (`ProvaMontada` com blocos e metadados JSON), `banco_frases` (`BancoFrases`), `audit_log_geracao` (`AuditLogGeracao`).

---

## 9. Principais Módulos do Backend

- `backend/app/main.py`: inicialização da API, CORS (`localhost:3000` / `127.0.0.1:3000`), criação de diretórios `avatars/` e `static/` e inclusão dos routers.
- `backend/app/database.py` e `backend/app/db_models.py`: camada assíncrona SQLAlchemy e definição ORM.
- `backend/app/auth.py` e `backend/app/security.py`: autenticação JWT, verificação de usuário ativo e helpers de escopo por tenant e sanitização de caminhos.
- `core/document_generator.py` e `core/docx_parser.py`: geração de provas/gabaritos em DOCX/PDF e extração estruturada de documentos Word.

---

## 10. Principais Endpoints da API

| Prefixo / Módulo | Endpoints Principais |
| :--- | :--- |
| **Auth** (`/auth`) | `POST /auth/login` |
| **Usuários** (`/users`) | `POST /users/register`, `GET /users/me`, `GET / POST /users/`, `PATCH / DELETE /users/{user_id}` |
| **Admin Tenants** (`admin_clients.py`) | `GET / POST /admin/clients`, `GET /admin/clients/dashboard`, `POST /admin/clients/{client_id}/create-admin`, `GET /admin/clients/{client_id}` |
| **Empresa** (`company.py`) | `GET / PUT /company` |
| **Eventos** (`/eventos`) | `GET / POST /eventos/`, `GET /eventos/{event_id}/detalhes`, `GET / PUT / DELETE /eventos/{event_id}` |
| **Cargos** (`cargos.py`, `cargos_import.py`) | `GET / POST /eventos/{event_id}/cargos`, `PUT / DELETE /cargos/{cargo_id}`, `POST /eventos/{event_id}/cargos/upload-capa-pdf`, `POST /eventos/{event_id}/cargos/import-csv` |
| **Conteúdos** (`/conteudos`) | `GET / POST /conteudos/eventos/{evento_id}/conteudos`, `PUT / DELETE /conteudos/{conteudo_id}`, `POST .../csv`, `GET /conteudos/meus` |
| **Questões** (`questoes.py`) | `GET / POST /eventos/{evento_id}/conteudos/{conteudo_id}/questoes`, `GET / PUT / DELETE /eventos/{evento_id}/conteudos/{conteudo_id}/questoes/{id_questao}`, `PATCH .../questoes/{id_questao}/revisao`, `GET .../questoes/{id_questao}/revisoes`, `POST .../importar-docx`, `POST .../importar-docx/confirmar` *(nota: `importador.py` não está montado em `main.py`)* |
| **Textos de Referência** (`textos_referencia.py`) | `GET / POST /eventos/{evento_id}/conteudos/{conteudo_id}/textos-referencia`, `GET / PATCH / DELETE /eventos/{evento_id}/conteudos/{conteudo_id}/textos-referencia/{id_texto_ref}` |
| **Frases** (`/frases`) | `GET / POST /frases/`, `PUT / DELETE /frases/{frase_id}`, `POST /frases/import/` |
| **Templates** (`/api`) | `GET / POST /api/eventos/{evento_id}/templates`, `GET / DELETE /api/eventos/{evento_id}/templates/{nome_arquivo}`, `POST /api/eventos/{evento_id}/templates/upload` |
| **Provas e Simulação** (`/provas`, `provas_geracao.py`) | `GET /provas/eventos/{id_evento}/cargos-com-status-prova`, `GET / POST / DELETE /provas/eventos/{id_evento}/provas-montadas/{id_cargo}`, `GET /provas/eventos/{id_evento}/disciplinas`, `GET /provas/eventos/{event_id}/cargos-quantidade-questoes`, `GET /eventos/{event_id}/cargos/provas-geracao`, `POST /eventos/{event_id}/provas/definir-geracao`, `POST /eventos/{event_id}/simular-frases/{cargo_id}`, `POST /eventos/{event_id}/simular-certo-errado/{cargo_id}` |
| **Gabaritos** (`/api/gabarito`) | `GET /api/gabarito/eventos/{evento_id}/cargos/{cargo_id}/gabarito`, `GET .../variacoes`, `GET .../exportacoes`, `POST /api/gabarito/eventos/{evento_id}/exportar-gabaritos-zip` |
| **Exportação** (`/api/export`) | `POST /api/export/eventos/{evento_id}/validar-senha`, `GET /api/export/eventos/{evento_id}/cargos/{cargo_id}/exportacoes`, `GET /api/export/download`, `POST /api/export/eventos/{evento_id}/cargos/{cargo_id}/gerar-arquivos`, `POST .../exportar-gabarito`, `POST /api/export/eventos/{evento_id}/cargos/gerar-arquivos-multiplos`, `GET /api/export/download-zip` |
| **Auditoria** (`/admin/logs/geracao`) | `GET / POST /admin/logs/geracao/` |
| **Apoio / IA** (`/api`) | `POST /api/ia-chat`, `POST /api/check-plagio`, `POST /api/dicionario`, `POST /api/biblioteca` |

---

## 11. Banco de Questões, Importação DOCX e Revisão

- **Tipos suportados**: `MULTIPLA_ESCOLHA` (`OpcoesQuestao`), `CERTO_ERRADO` (`ItensVerdadeiroFalso`), `DISCURSIVA` e `SUBJETIVA` (`DetalhesQuestaoDiscursiva`).
- **Importação DOCX**: `core/docx_parser.py` (`DocxParser`) extrai texto formatado, tabelas e mídias de `.docx`, permitindo pré-visualização e confirmação para persistência no banco (`questoes.py`).
- **Revisão**: O fluxo de revisão altera `status_revisao`/`observacao_revisor` e grava histórico em `HistoricoRevisaoQuestao`.

---

## 12. Montagem, Geração de Provas, Gabaritos e Exportação

- **Montagem**: `ProvasMontadas` armazena `blocos_questoes` e `metadados_prova` (JSON) por evento/cargo.
- **Geração e Variações**: `provas_geracao.py` configura número de variações, embaralhamento de questões/alternativas e simulações.
- **Exportação DOCX/PDF/ZIP**: `exportacao.py` utiliza `DocumentGenerator` (`core/document_generator.py`) para montar o DOCX (com `html_to_docx.py`), converte para PDF via LibreOffice, preenche capas AcroForm com `PreencheCapaPDF_JSON_PDFBox.java` (`campos_capa.py`), gera gabaritos (`gabarito.py`) e compacta pacotes com `pyzipper`.

---

## 13. Integrações Externas

- **OpenAI API** (`backend/app/routes/ia_chat.py`): utiliza `gpt-3.5-turbo` (requer `OPENAI_API_KEY`).
- **Bing Web Search API v7** (`backend/app/routes/plagio.py`): verificação de similaridade/plágio (requer `BING_API_KEY`).
- **Google reCAPTCHA** (`backend/app/routes/auth.py`): validação de login (requer `RECAPTCHA_SECRET_KEY`).
- **Dicio (`dicio.com.br`)** (`backend/app/routes/dicionario.py`): consulta via requisição HTTP e regex sobre HTML.

---

## 14. Segurança e Isolamento Multi-Tenant

- **Autenticação**: JWT (`HS256`, expiração 30 min) com `JWT_SECRET_KEY` via `.env`, senhas com `bcrypt` e bloqueio de usuários inativos.
- **Criptografia**: `Fernet` (`FERNET_KEY`) para senhas de eventos e vínculos. Validação de senha de evento usa `hmac.compare_digest`.
- **Prevenção de Path Traversal e Escalação**: `backend/app/security.py` fornece `nome_arquivo_seguro`, `caminho_dentro_de` e `evento_autorizado`; `/users/register` bloqueia cadastro público em papéis administrativos.
- **Isolamento Multi-Tenant**: Atualmente aplicado na camada de aplicação por filtro de `tenant_id` (ainda com rotas a auditar quanto à obrigatoriedade estrita de RBAC e escopo). **O isolamento multi-tenant ainda não pode ser considerado garantido**, pois não há testes automatizados validando isolamento entre dois tenants (Tenant A vs. Tenant B). No PostgreSQL, `backend/app/rls_policies.sql` declara RLS para as **16 tabelas com `tenant_id`** (excluindo `tenants`, que é a tabela global de clientes), e `backend/app/database.py` expõe `set_tenant_context`, porém essa camada **ainda não foi validada em execução** e requer role não-superuser + dependência de sessão nas rotas.
- **LGPD**: Campos pessoais/bancários (`cpf`, `pix_key`, `banco`, `agencia`, `conta_corrente`) ainda não possuem criptografia em repouso dedicada nem mascaramento em logs.

---

## 15. Instalação, Variáveis de Ambiente e Execução

### Pré-requisitos
- Python 3.10+ (validado com CPython `3.11.0` no `.venv` da raiz; `backend/requirements.txt` está incompleto, portanto um ambiente novo exigirá instalar também as dependências ausentes desse arquivo)
- PostgreSQL 16+ (o `docker-compose.yml` provisiona `postgres:16-alpine`; também compatível com instalação local mais recente, como PostgreSQL 17 observado no ambiente)
- LibreOffice (para conversão DOCX → PDF em `PdfConverter`) e Java JRE/JDK (para `PreencheCapaPDF_JSON_PDFBox`)
- Node.js 18+ (para servir `frontend/build/` ou reconstruir quando `frontend/src/` for restaurado)

### Variáveis de Ambiente (`.env`)
Configurar na raiz do projeto (sem versionar segredos):
```env
FERNET_KEY=<chave-fernet-base64>
JWT_SECRET_KEY=<chave-secreta-forte>
RECAPTCHA_SECRET_KEY=<chave-secreta-recaptcha>
OPENAI_API_KEY=<opcional-para-ia-chat>
BING_API_KEY=<opcional-para-plagio>
# Opcional (se omitido, usa SQLite local diagprooff.db):
DATABASE_URL=postgresql+asyncpg://diagpro_admin:diagpro_dev_password@localhost:5432/diagpro
```

### Execução Local (Validada em Ambiente)
Subir o backend FastAPI usando o `.venv` da raiz:
```powershell
.\.venv\Scripts\uvicorn.exe backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
API disponível em `http://127.0.0.1:8000` e Swagger em `http://127.0.0.1:8000/docs`.

Servir o build estático existente do frontend (`frontend/build/`):
```powershell
npx serve -s frontend/build -l 3000
```

### Migração Estruturada para PostgreSQL (Não Executada Nesta Auditoria)
> **Observação:** `alembic/versions/` ainda não possui revisões geradas. A sequência abaixo cria o schema via Alembic antes de popular os dados do SQLite (não utilize `stamp head` sem executar `upgrade head`):

```powershell
# 1. Subir o PostgreSQL (e configurar DATABASE_URL no .env)
docker compose up -d db

# 2. Gerar a revisão inicial a partir dos modelos ORM e aplicá-la no banco vazio
.\.venv\Scripts\alembic.exe revision --autogenerate -m "initial_postgres_multitenant"
.\.venv\Scripts\alembic.exe upgrade head

# 3. Migrar os dados do diagprooff.db e aplicar backend/app/rls_policies.sql
.\.venv\Scripts\python.exe scripts/migrate_sqlite_to_postgres.py
```

---

## 16. Testes e Validação

- **Suíte de testes automatizados:** Não identificada no repositório (não há `pytest` nem testes de unidade/integração; `backend/app/test_upload.py` é apenas um protótipo de 7 linhas).
- **Verificações executadas nesta auditoria:**
  - `.\.venv\Scripts\uvicorn.exe --version` → `Running uvicorn 0.37.0 with CPython 3.11.0 on Windows`
  - `.\.venv\Scripts\alembic.exe --version` → `alembic 1.20.1`
  - `.\.venv\Scripts\python.exe -m py_compile backend/app/main.py backend/app/database.py backend/app/db_models.py backend/app/auth.py backend/app/security.py` → concluído com código `0`.
  - Testes E2E de banco PostgreSQL/RLS, geração real de PDF/ZIP e UI frontend **não foram executados** nesta auditoria.

---

## 17. Limitações Conhecidas e Roadmap Técnico

### Limitações Atuais
- `frontend/src/` e `frontend/public/` ausentes no repositório local (apenas `frontend/build/` disponível).
- `backend/requirements.txt` incompleto frente às bibliotecas importadas pelo código.
- Ausência de suíte de testes automatizados (`pytest`), rate limiting e refresh tokens em cookie `HttpOnly`.
- `biblioteca.py` usa dados fictícios (`QUESTOES_FAKE`) e `dicionario.py` depende de scraping HTML.
- Geração de arquivos (DOCX/PDF/PDFBox/ZIP) executada de forma síncrona na requisição HTTP.
- Arquivos em `avatars/` e `static/` montados diretamente via `StaticFiles` sem controle de acesso por endpoint.

### Próximos Passos Prioritários
1. **Concluir migração PostgreSQL + RLS**: rodar migração de dados, criar usuário PostgreSQL não-superuser (`diagpro_runtime`) e aplicar `set_tenant_context` como dependência global nas rotas.
2. **Auditoria completa de RBAC e LGPD**: revisar todas as rotas para checagem estrita de `UserRole`, adicionar rate limiting (`slowapi`), refresh token `HttpOnly` e criptografia em repouso para dados bancários/CPF.
3. **Restaurar código-fonte do Frontend**: recuperar `frontend/src/` e `frontend/public/` com sanitização (`DOMPurify`).
4. **Suíte de Testes e CI/CD**: criar testes `pytest` de isolamento Tenant A vs Tenant B e matriz RBAC, atualizar `requirements.txt` e configurar pipeline CI (`ruff`, `bandit`, `pip-audit`).
5. **Escala**: mover geração de provas para fila assíncrona (Redis + ARQ/Celery) e mídias/provas para Object Storage (S3/MinIO) com URLs pré-assinadas.

---

## 18. Diretrizes para Desenvolvimento e Contribuição

- **Fonte da verdade:** código-fonte, modelos, rotas e migrações atuais prevalecem sobre documentos antigos.
- **Isolamento multi-tenant:** nunca confiar em `tenant_id` enviado pelo cliente; derivar sempre do usuário autenticado e validar pertencimento ao evento/recurso.
- **Segurança por padrão:** toda nova rota deve exigir autenticação e verificação explícita de `UserRole`, além de testes negativos e de isolamento entre tenants.
- **Preservação de segredos:** nunca registrar senhas, chaves (`JWT_SECRET_KEY`, `FERNET_KEY`), tokens ou dados pessoais em código, logs ou commits.
