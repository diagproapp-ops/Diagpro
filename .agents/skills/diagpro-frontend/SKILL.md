---
name: diagpro-frontend
description: Desenvolve, recupera e mantém a interface web do DiagPro, incluindo arquitetura frontend, integração com API, autenticação, RBAC visual, formulários, acessibilidade, estados e prevenção de XSS.
---

# Frontend do DiagPro

## Cuidado com o estado conhecido
O relatório informa que `frontend/src/` e `frontend/public/` estavam ausentes no repositório local analisado e que existia `frontend/build/`. Não presuma React, Vue, Vite, Next.js, TypeScript ou qualquer versão até inspecionar `package.json`, lockfile, build e histórico disponível. Se o código-fonte realmente estiver ausente, primeiro avalie recuperação a partir de Git, backup ou artefatos; não tente reconstruir telas silenciosamente a partir do build.

## Procedimento
1. Inspecione estrutura, `package.json`, lockfile, rotas, componentes, estilos, testes e configuração de build.
2. Identifique contratos reais da API e os fluxos de usuário por role.
3. Preserve identidade visual e padrões existentes; antes de criar design system, inventarie componentes.
4. Implemente estados de carregamento, vazio, erro, sucesso, validação e permissão negada.
5. Trate RBAC visual apenas como UX: o backend continua sendo a autoridade de autorização.
6. Centralize cliente HTTP, tratamento de expiração, erros e configuração de ambiente; não exponha segredos no bundle.
7. Valide formulários no cliente para UX e no servidor para segurança.
8. Renderize conteúdo de questões/textos ricos com sanitização robusta (o relatório cita DOMPurify como pendência); nunca use HTML não confiável sem sanitização.
9. Garanta acessibilidade: navegação por teclado, foco visível, labels, contraste, mensagens de erro associadas e semântica.
10. Teste fluxos por role e cenários de API 401/403/404/422/500, sessão expirada e tenant sem dados.

## Áreas funcionais
- Administração geral de tenants/clientes.
- Administração da banca, equipe e perfis.
- Eventos, cargos, disciplinas e conteúdos.
- Banco de questões, textos de referência e revisão.
- Montagem/geração de provas e simulações.
- Visualização de gabaritos e exportações.
- Ferramentas auxiliares.

## Regras
- Não invente telas, endpoints ou payloads: confirme no backend.
- Não armazene tokens sensíveis em localStorage sem avaliação explícita de risco; prefira arquitetura de sessão segura compatível com backend.
- Não confie em IDs/tenant vindos da URL para autorização.
- Não exponha CPF, PIX ou dados bancários desnecessariamente.
- Não remova funcionalidades existentes para simplificar a interface.
- Não declare frontend restaurado até que código-fonte, build reproduzível e testes estejam verificados.
