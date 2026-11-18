# Regras permanentes do projeto DiagPro

Estas regras são sempre aplicáveis a qualquer alteração neste repositório.

## Produto
DiagPro é uma plataforma multi-tenant para gestão de concursos públicos e avaliações. Seus dados e artefatos — questões, gabaritos, provas, capas, credenciais e informações de colaboradores — são críticos e confidenciais.

## Fonte da verdade
O código, migrations, testes, contratos e configuração atuais são a fonte da verdade. O relatório técnico inicial é um mapa de contexto, não prova de implementação atual. Verifique antes de afirmar.

## Segurança
- Nunca confie em `tenant_id` enviado pelo cliente.
- Toda consulta/alteração deve respeitar tenant, evento, recurso e role.
- Negação por padrão; backend é a autoridade de autorização.
- Nunca desative RLS, autenticação, autorização, validação ou auditoria para contornar problemas.
- Nunca exponha segredos ou dados pessoais em código, logs, testes ou respostas.

## Mudanças
- Inspecione antes de editar.
- Faça plano e diff pequeno.
- Preserve contratos e dados.
- Migrações destrutivas, operações de produção, rotação de chaves e deploy exigem autorização explícita, backup e rollback.
- Não invente funcionalidades nem marque pendências como concluídas sem evidência.

## Qualidade
- Inclua testes para comportamento novo e cenários negativos.
- Teste isolamento Tenant A/Tenant B e matriz RBAC nas áreas afetadas.
- Informe comandos realmente executados e resultados.
- Revise o diff final para segurança, regressões e compatibilidade.

## Skills
Use as skills especializadas em `.agents/skills/` conforme o domínio. Para tarefas que cruzem domínios, combine as skills relevantes e use `diagpro-orchestrator` para coordenar.
