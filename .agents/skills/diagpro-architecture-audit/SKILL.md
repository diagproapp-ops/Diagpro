---
name: diagpro-architecture-audit
description: Audita arquitetura, dependências, dívida técnica e fronteiras entre API web, núcleo documental e legado desktop do DiagPro antes de refatorações ou expansão.
---

# Auditoria arquitetural do DiagPro

## Contexto do relatório
O relatório descreve `core/document_generator.py` com cerca de 3.251 linhas e classes `DocxProofGenerator`, `ArchiveManager`, `AnswerKeyGenerator`, `PdfConverter` e `DocumentGenerator`; cita `docx_parser.py`, `utils.py` e módulos legados desktop (`app_controller.py`, `event_manager.py`, `frase_manager.py`, `diagram_manager.py`). Também aponta imports `customtkinter`/`tkinter` nos fluxos usados pela API como dívida técnica.

## Método
1. Faça mapa de dependências real (imports, chamadas, dados, jobs).
2. Identifique código compartilhado pela API e pelo desktop.
3. Separe regra de domínio de interface, transporte HTTP, filesystem e subprocessos.
4. Antes de mover código, mapeie todos os consumidores e compatibilidade.
5. Extraia módulos em passos pequenos, mantendo interfaces e testes de caracterização.
6. Não faça reescrita total de `document_generator.py` sem inventário de responsabilidades e testes de equivalência.
7. Verifique dependências não utilizadas, duplicadas, vulneráveis e incompatíveis com Python/Java/LibreOffice.
8. Atualize diagrama/documentação apenas com arquitetura observada.

## Saída esperada
- mapa de módulos e dependências;
- riscos e acoplamentos;
- proposta incremental;
- arquivos afetados;
- testes de caracterização;
- plano de rollback.
