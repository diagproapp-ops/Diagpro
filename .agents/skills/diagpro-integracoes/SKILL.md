---
name: diagpro-integracoes
description: Mantém integrações do DiagPro com OpenAI, busca de plágio, dicionário e biblioteca de questões, incluindo timeouts, limites, privacidade, custos e resiliência.
---

# Integrações externas e ferramentas auxiliares

## Contexto do relatório
O relatório cita `ia_chat.py` com OpenAI e `gpt-3.5-turbo`, `plagio.py` com Bing Web Search API v7, `dicionario.py` com scraping de `dicio.com.br` via requests/regex e `biblioteca.py` com lista estática `QUESTOES_FAKE`. Trate isso como estado descrito no relatório, não como confirmação atual. Verifique SDKs, modelos, contratos e disponibilidade antes de alterar.

## Regras comuns
- Credenciais somente no ambiente/secret manager.
- Timeouts explícitos, limites de tamanho, rate limiting e tratamento de indisponibilidade.
- Não enviar CPF, PIX, dados bancários, credenciais, conteúdo confidencial ou dados identificáveis a terceiros sem base legal, finalidade e autorização apropriadas.
- Minimize o contexto enviado à IA e informe claramente ao usuário quando conteúdo for transmitido a serviço externo.
- Trate respostas externas como não confiáveis; valide e sanitize antes de exibir ou persistir.
- Controle custos, tokens, retries e concorrência.
- Não afirme que plágio foi comprovado por percentual automatizado; similaridade é indício para análise humana.

## OpenAI/chat
- Inspecione SDK e modelo atualmente configurados; não mantenha automaticamente um modelo legado se estiver obsoleto.
- Defina timeout, limite de tokens, tratamento de erro, rate limit e observabilidade sem registrar prompts sensíveis.
- Delimite claramente o contexto da questão e a pergunta do usuário.
- IA não deve alterar gabaritos, aprovar questões ou executar ações administrativas sem confirmação humana.

## Busca de similaridade/plágio
- Documente fonte, data, limites e método de cálculo.
- Evite apresentar percentual como prova conclusiva.
- Trate falhas de API, quotas e resultados parciais de modo explícito.
- Respeite termos de uso, privacidade e limites do provedor.

## Dicionário
- Prefira API/fonte estável e permitida a scraping frágil; use cache e timeout.
- Não dependa de regex sobre HTML instável sem testes e fallback claro.

## Biblioteca de questões
- Substitua dados estáticos apenas após definir modelo de dados, origem, direitos de uso, filtros, tenant/escopo de compartilhamento e critérios de busca.
- Não misture questões privadas de um tenant com biblioteca compartilhada.
- Registre proveniência/licença quando aplicável.
