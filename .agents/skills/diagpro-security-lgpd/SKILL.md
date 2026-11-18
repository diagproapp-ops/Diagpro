---
name: diagpro-security-lgpd
description: Audita e implementa segurança no DiagPro: autenticação JWT, RBAC, isolamento por tenant, LGPD, criptografia, uploads, arquivos, CORS, headers, rate limiting e proteção contra vulnerabilidades.
---

# Segurança e LGPD do DiagPro

## Princípio
Segurança é requisito transversal. Faça threat modeling proporcional ao impacto e não trate a existência de um helper como prova de que todas as rotas estão protegidas.

## Contexto do relatório
O relatório descreve bcrypt, JWT HS256, `JWT_SECRET_KEY` em `.env`, bloqueio de usuários inativos, reCAPTCHA, `Fernet`, autorização por evento, prevenção de path traversal e algumas rotas de apoio protegidas. Pendências descritas: auditoria RBAC/tenant em 100% das rotas, refresh token HttpOnly/Secure/SameSite com CSRF, rate limiting, criptografia de dados pessoais/bancários, arquivos privados, headers e CORS restrito.

## Matriz de autorização
Roles: `ADMIN_GERAL`, `ADMIN`, `PROFESSOR`, `REVISOR`, `DIAGRAMADOR`.
Antes de alterar endpoint, determine:
- quem pode executar a ação;
- em qual tenant/evento/cargo/recurso;
- se o usuário é dono/responsável pelo recurso;
- se a ação exige trilha de auditoria;
- se há transição de estado válida (ex.: questão em revisão/aprovada/reprovada).
Use negação por padrão. Não invente permissões; derive do código e dos requisitos existentes e sinalize lacunas.

## Controles obrigatórios
- Autenticação: validar assinatura, expiração, issuer/audience quando configurados, algoritmo fixo e claims. Não aceitar tokens com algoritmo escolhido pelo cliente. Segredos fortes e fora do repositório.
- Sessão: se implementar refresh em cookie, definir estratégia CSRF, rotação/revogação e política de expiração; não introduzir cookies sem avaliar CORS e frontend.
- Senhas: hash adaptativo adequado; nunca criptografar senhas reversivelmente.
- Dados pessoais: classificar CPF, PIX, banco, agência e conta; definir finalidade, acesso mínimo, retenção, logs sem dados integrais, criptografia em repouso e gestão/rotação de chaves. Validar requisitos legais com responsável jurídico/privacidade; não alegar conformidade LGPD apenas por implementar criptografia.
- Arquivos: validar extensão, MIME real e conteúdo; impor limites; gerar nomes internos; armazenar fora da raiz pública; checar autorização em download; prevenir traversal, symlink e overwrite; varrer conteúdo quando viável.
- HTML rico/TipTap: sanitizar no servidor e/ou no ponto de renderização com allowlist; proteger contra XSS armazenado. Não confiar apenas no frontend.
- CORS: origens explícitas, métodos/headers mínimos, credenciais apenas quando necessário.
- Headers: CSP compatível com a aplicação, HSTS em HTTPS, `X-Content-Type-Options: nosniff`, política anti-framing adequada e Referrer-Policy.
- Rate limit: login, cadastro, validação de senha do evento, IA e serviços externos; limites por IP e identidade, com proteção distribuída quando houver múltiplas instâncias.
- Auditoria: registrar ator, tenant, recurso, ação, resultado, timestamp e correlation/request id; não registrar tokens, senhas, conteúdo sensível integral ou segredos.

## Procedimento
1. Mapeie ativo, ameaça, entrada, privilégio, fronteira de confiança e impacto.
2. Inspecione dependências e controles existentes antes de adicionar bibliotecas.
3. Corrija causa raiz; não esconda falha com tratamento genérico.
4. Crie testes negativos: usuário anônimo, role errada, tenant errado, recurso de outro evento, payload malicioso, arquivo inválido e abuso de taxa.
5. Revise logs, respostas e mensagens para evitar enumeração de usuários/tenants e exposição de dados.
6. Documente riscos residuais e configuração necessária.

## Não fazer
- Não desabilitar RLS, CSRF, validação ou autorização para facilitar testes.
- Não incluir chaves reais em `.env.example`, código, fixtures ou screenshots.
- Não afirmar que o sistema está “100% seguro” ou “em conformidade LGPD” sem avaliação abrangente.
