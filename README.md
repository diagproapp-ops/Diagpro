# 🏥 DiagPro - Sistema de Diagnóstico Profissional

> Sistema completo de gestão de diagnósticos com integração de Inteligência Artificial para análise e geração automatizada de documentação técnica.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-Private-red.svg)]()

---

## 📋 **Índice**

- [Sobre o Projeto](#sobre-o-projeto)
- [Stack Tecnológica](#stack-tecnológica)
- [Arquitetura](#arquitetura)
- [Funcionalidades](#funcionalidades)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Módulos Principais](#módulos-principais)
- [Instalação](#instalação)
- [Uso](#uso)
- [API](#api)
- [Segurança](#segurança)
- [Métricas](#métricas)
- [Contato](#contato)

---

## 🎯 **Sobre o Projeto**

O **DiagPro** é uma solução full-stack desenvolvida para automatizar e otimizar processos de diagnóstico profissional. O sistema combina:

- 🤖 **Inteligência Artificial** (OpenAI GPT-4)
- 📊 **Análise de Dados Complexos**
- 📝 **Geração Automática de Documentos**
- 🎨 **Interface Moderna e Responsiva**
- 🔒 **Segurança de Nível Empresarial**

### **Objetivos:**
- ✅ Automatizar processos de diagnóstico
- ✅ Reduzir tempo de análise em 70%
- ✅ Gerar documentação padronizada
- ✅ Integrar IA para insights inteligentes
- ✅ Centralizar gestão de eventos

---

## 💻 **Stack Tecnológica**

### **Backend**
```python
FastAPI        # Framework web moderno e rápido
Uvicorn        # Servidor ASGI de alta performance
OpenAI         # Integração com GPT-4
SQLite         # Banco de dados relacional
Python-dotenv  # Gerenciamento de variáveis de ambiente
```

### **Frontend**
```javascript
React           # Framework para interface
Mammoth         # Processamento de documentos DOCX
React-Markdown  # Renderização de Markdown
TypeScript      # Tipagem estática
```

### **Banco de Dados**
```
SQLite 3.x com WAL mode
- Diagprooff.db (2MB+ com dados)
- Schemas otimizados
- Relacionamentos complexos
```

---

## 🏗️ **Arquitetura**

```
┌─────────────────────────────────────────┐
│          FRONTEND (React)               │
│  - Interface do Usuário                 │
│  - Visualização de Dados                │
│  - Markdown Rendering                   │
└──────────────┬──────────────────────────┘
               │ HTTP/REST API
┌──────────────▼──────────────────────────┐
│       BACKEND (FastAPI/Python)          │
│  ┌────────────────────────────────┐     │
│  │   Controllers & Routes         │     │
│  ├────────────────────────────────┤     │
│  │    Business Logic (Core)       │     │
│  │  - Event Manager (156KB)       │     │
│  │  - Document Generator (160KB)  │     │
│  │  - Diagram Manager             │     │
│  │  - Auth Service                │     │
│  ├────────────────────────────────┤     │
│  │    Data Layer                  │     │
│  │  - Database Setup (20KB)       │     │
│  │  - Models & Utils (42KB)       │     │
│  └────────────────────────────────┘     │
└───────────┬──────────────────────────────┘
┌───────────▼──────────────────────────────┐
│   SQLite Database + OpenAI Integration   │
└──────────────────────────────────────────┘
```

**Padrão:** MVC + Service Layer + Repository Pattern

---

## ⚙️ **Funcionalidades**

### **🎯 Gestão de Eventos**
- CRUD completo de eventos
- Categorização e tags inteligentes
- Sistema de templates personalizáveis
- Histórico e auditoria completa
- Busca avançada com filtros

### **📄 Geração de Documentos**
- Geração automática de relatórios
- Exportação em múltiplos formatos (PDF/DOCX)
- Templates customizáveis
- Parsing de documentos DOCX
- Renderização de Markdown

### **🎨 Gerenciamento de Diagramas**
- Criação visual de diagramas
- Edição interativa
- Exportação de imagens
- Integração com eventos

### **🤖 Integração com IA**
- Análise inteligente de diagnósticos
- Sugestões automatizadas
- Geração de textos contextuais
- Processamento de linguagem natural

### **🔒 Sistema de Autenticação**
- Login/Logout seguro
- Hash de senhas (bcrypt)
- Sessões de usuário
- Níveis de permissão (RBAC)
- Recuperação de senha

---

## 📁 **Estrutura do Projeto**

```
DiagPro/
│
├── 📂 backend/                    # Backend Python/FastAPI
│   ├── 📂 app/                    # Aplicação principal
│   ├── 📄 requirements.txt        # Dependências Python
│   └── 📄 __init__.py
│
├── 📂 core/                       # Lógica de negócio (40,000+ linhas)
│   ├── 📄 app_controller.py       # Controller principal (60KB)
│   ├── 📄 auth_service.py         # Autenticação e autorização
│   ├── 📄 config_manager.py       # Configurações do sistema
│   ├── 📄 database_setup.py       # Setup do banco (20KB)
│   ├── 📄 document_generator.py   # Geração de docs (160KB)
│   ├── 📄 event_manager.py        # Gestão de eventos (156KB)
│   ├── 📄 diagram_manager.py      # Gestão de diagramas
│   ├── 📄 docx_parser.py          # Parser DOCX (38KB)
│   ├── 📄 utils.py                # Utilitários (42KB)
│   └── 📄 models.py               # Modelos de dados
│
├── 📂 avatars/                    # Imagens de avatares
├── 📂 material/                   # Recursos e materiais
├── 📂 static/                     # Arquivos estáticos
├── 📂 templates_eventos/          # Templates de eventos
│
├── 📄 diagprooff.db               # Banco de dados (2MB+)
├── 📄 create_db.py                # Script de setup do BD
├── 📄 update_password.py          # Utilitário de senhas
├── 📄 package.json                # Dependências Node.js
└── 📄 .gitignore
```

---

## 🧩 **Módulos Principais**

| Módulo | Tamanho | Responsabilidade |
|--------|---------|------------------|
| **event_manager.py** | 156 KB | Gestão completa de eventos, templates, validações |
| **document_generator.py** | 160 KB | Geração de PDFs, formatação, inserção de gráficos |
| **app_controller.py** | 60 KB | Controle de rotas, orquestração, middleware |
| **utils.py** | 42 KB | Validação, formatação, helpers diversos |
| **docx_parser.py** | 38 KB | Conversão DOCX → HTML/Markdown |
| **database_setup.py** | 20 KB | Schemas, relacionamentos, constraints |

**Total:** 40,000+ linhas de código Python

---

## 🚀 **Instalação**

### **Pré-requisitos:**
- Python 3.10+
- Node.js 18+
- SQLite 3.x

### **Backend:**
```bash
# Clone o repositório (requer acesso)
git clone https://github.com/vhugo1234/DiagPro.git
cd DiagPro

# Crie ambiente virtual
python -m venv backend/venv
source backend/venv/bin/activate  # Windows: backend\venv\Scripts\activate

# Instale dependências
cd backend
pip install -r requirements.txt

# Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais

# Inicie o servidor
uvicorn app.main:app --reload
```

### **Frontend:**
```bash
# Instale dependências
npm install

# Inicie em desenvolvimento
npm run dev

# Build para produção
npm run build
```

### **Banco de Dados:**
```bash
# Crie estrutura inicial
python create_db.py
```

---

## 🎮 **Uso**

### **Desenvolvimento:**
```bash
# Backend (porta 8000)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (porta 3000)
npm run dev
```

### **Produção:**
```bash
# Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Frontend
npm run build
npm start
```

### **Acesse:**
- Frontend: `http://localhost:3000`
- API Docs: `http://localhost:8000/docs`
- Redoc: `http://localhost:8000/redoc`

---

## 🔌 **API**

### **Endpoints Principais:**

#### **Autenticação:**
```http
POST   /api/auth/login          # Login de usuário
POST   /api/auth/logout         # Logout
POST   /api/auth/register       # Registro
```

#### **Eventos:**
```http
GET    /api/eventos             # Lista eventos
GET    /api/eventos/{id}        # Detalhes do evento
POST   /api/eventos             # Cria evento
PUT    /api/eventos/{id}        # Atualiza evento
DELETE /api/eventos/{id}        # Remove evento
```

#### **Documentos:**
```http
GET    /api/documentos          # Lista documentos
POST   /api/documentos/gerar    # Gera documento
GET    /api/documentos/{id}     # Download
```

#### **IA:**
```http
POST   /api/ai/analisar         # Análise com IA
POST   /api/ai/sugestoes        # Sugestões inteligentes
```

**Documentação completa:** `/docs` (Swagger UI)

---

## 🔒 **Segurança**

### **Implementações:**
- ✅ Hash de senhas com bcrypt
- ✅ Proteção contra SQL Injection
- ✅ Sanitização de inputs (XSS)
- ✅ CSRF tokens
- ✅ Rate limiting
- ✅ HTTPS obrigatório (produção)
- ✅ Variáveis de ambiente (.env)
- ✅ CORS configurado

### **Autenticação:**
```python
# JWT tokens
# Role-based access control (RBAC)
# Session management
# Password strength validation
```

---

## 📊 **Métricas**

### **Estatísticas do Código:**
```
Arquivos Python:        20+
Linhas de código:       40,000+
Tamanho do banco:       2MB (com dados)
Módulos principais:     15
Endpoints API:          25+
Integração com IA:      OpenAI GPT-4
```

### **Complexidade dos Módulos:**
```
document_generator.py   ████████████ 160 KB
event_manager.py        ███████████▌ 156 KB
app_controller.py       ████▌        60 KB
utils.py                ███          42 KB
docx_parser.py          ██▌          38 KB
database_setup.py       █▌           20 KB
```

### **Performance:**
- ⚡ FastAPI: Um dos frameworks mais rápidos
- 🚀 Async/await para operações paralelas
- 💾 SQLite otimizado com WAL mode
- 🔄 Cache inteligente

---

## 🌟 **Diferenciais Técnicos**

### **1. Arquitetura Modular**
- Separação clara de responsabilidades
- Componentes reutilizáveis
- Fácil manutenção e escalabilidade

### **2. Integração com IA**
- GPT-4 para análises contextuais
- Sugestões inteligentes em tempo real
- Geração automática de textos

### **3. Performance Otimizada**
- FastAPI (framework assíncrono)
- Queries SQL otimizadas
- Cache estratégico

### **4. Processamento Avançado**
- Conversão DOCX → HTML/Markdown
- Geração de PDFs profissionais
- Templates personalizáveis

### **5. Developer Experience**
- Documentação automática (Swagger)
- Type hints (Python + TypeScript)
- Hot reload em desenvolvimento
- Scripts utilitários

---

## 🎯 **Casos de Uso**

### **Fluxo 1: Criar Diagnóstico**
1. Usuário autentica no sistema
2. Acessa módulo de eventos
3. Cria novo evento com dados
4. IA analisa e sugere diagnóstico
5. Usuário revisa e aprova
6. Sistema gera documento final
7. Exporta em formato desejado

### **Fluxo 2: Gerar Relatório Periódico**
1. Seleciona eventos do período
2. Escolhe template de relatório
3. Sistema compila dados automaticamente
4. IA enriquece com insights
5. Gera documento formatado
6. Download/compartilhamento

---

## 📦 **Dependências**

### **Backend (requirements.txt):**
```txt
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
openai>=1.0.0
requests>=2.31.0
python-dotenv>=1.0.0
```

### **Frontend (package.json):**
```json
{
  "dependencies": {
    "mammoth": "^1.11.0",
    "react-markdown": "^10.1.0"
  },
  "devDependencies": {
    "@types/uuid": "^10.0.0"
  }
}
```

---

## 🛠️ **Scripts Utilitários**

### **create_db.py**
Cria estrutura inicial do banco de dados com dados de exemplo.

### **update_password.py**
Atualiza senha de usuário com hash seguro.

### **print_routes.py**
Lista todas as rotas da API para debug.

---

## 📈 **Roadmap**

### **✅ Implementado:**
- API RESTful completa
- Autenticação e autorização
- CRUD de eventos
- Geração de documentos
- Integração OpenAI
- Processamento DOCX
- Sistema de diagramas

### **🔜 Próximos Passos:**
- WebSockets para real-time
- Containerização (Docker)
- CI/CD pipeline
- Testes automatizados (pytest)
- Cache com Redis
- Filas (Celery)

---

## 🤝 **Contribuindo**

Este é um projeto privado. Para contribuições, entre em contato.

---

## 📄 **Licença**

Este projeto é **privado** e proprietário.  
© 2024 Victor Hugo Ramos. Todos os direitos reservados.

---

## 👨‍💻 **Desenvolvedor**

**Victor Hugo Ramos**

[![GitHub](https://img.shields.io/badge/GitHub-vhugo1234-181717?logo=github)](https://github.com/vhugo1234)
[![Portfolio](https://img.shields.io/badge/Portfolio-Visite-blue?logo=vercel)](https://portfolio-victor-hugo-ramos.vercel.app)

---

## 📞 **Contato**

Para demonstrações, dúvidas ou oportunidades:

📧 **Email:** [seu-email@exemplo.com]  
💼 **LinkedIn:** [seu-linkedin]  
🌐 **Portfolio:** [https://portfolio-victor-hugo-ramos.vercel.app](https://portfolio-victor-hugo-ramos.vercel.app)

---

## 🙏 **Agradecimentos**

- OpenAI pela API GPT-4
- FastAPI pela documentação excelente
- Comunidade Python e React

---

<div align="center">

**Desenvolvido com ❤️ por Victor Hugo Ramos**

[![Python](https://img.shields.io/badge/Made%20with-Python-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Powered%20by-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/UI%20with-React-61DAFB?logo=react)](https://reactjs.org/)

</div>
