---
name: diagpro-provas-documentos
description: Mantém montagem e geração de provas do DiagPro, blocos, embaralhamento, variações, balanceamento certo/errado, frases, gabaritos, DOCX, PDF, capas, PDFBox, ZIP criptografado e auditoria.
---

# Montagem e geração de provas

## Contexto descrito
O relatório cita `ProvasMontadas`, `provas_geracao.py`, `document_generator.py`, `gabarito.py`, `html_to_docx.py`, `PdfConverter`, PDFBox Java, `pyzipper` e `audit_log_geracao`. A geração envolve DOCX → PDF, preenchimento de capas PDF, gabaritos e ZIP.

## Integridade de prova
- A prova gerada deve corresponder à estrutura aprovada e às regras do cargo/evento.
- Preserve disciplina, ordem, quantidade, peso, tipo de conhecimento, textos de referência e metadados.
- Variações/embaralhamento precisam ter regra explícita e determinística quando houver `seed`.
- Não altere a correspondência entre número da questão, alternativa correta e gabarito ao embaralhar.
- Simulações de frases e distribuição Certo/Errado não podem ser confundidas com geração final.
- Valide limites e consistência antes de iniciar exportação; falhas devem ser explícitas.

## Procedimento de geração
1. Carregue evento/cargo e valide tenant, autorização, estado e parâmetros.
2. Valide quantidades por disciplina, questões disponíveis/aprovadas e regras de variação.
3. Gere/registre `seed` e parâmetros necessários para reprodução, sem expor segredos.
4. Monte artefatos temporários em diretório isolado por job e com nomes seguros.
5. Gere DOCX preservando estilos, colunas, cabeçalho/rodapé, imagens, numeração e textos de referência.
6. Converta via LibreOffice em ambiente controlado; trate timeout, processo travado e falha de conversão.
7. Preencha AcroForm com PDFBox e valide campos obrigatórios; flatten somente após confirmação do preenchimento.
8. Gere gabaritos e valide consistência com cada variação.
9. Empacote ZIP criptografado conforme requisito e verifique integridade do arquivo final.
10. Grave auditoria: ator, tenant, evento, cargo, ação, parâmetros, seed, resultado, timestamp, request/job id e metadados seguros.
11. Limpe temporários mesmo em falhas, sem apagar artefatos finais nem arquivos de outros jobs.

## Segurança e confiabilidade
- Não exponha download sem autorização por tenant/evento/cargo.
- Não registre senhas de evento ou chaves em auditoria.
- Não confie em nomes de arquivo fornecidos pelo cliente.
- Evite colisão de diretórios/nomes entre jobs concorrentes.
- Operações pesadas devem ser avaliadas para workers (ARQ ou Celery + Redis, pendência no relatório); não implemente fila sem idempotência, estado do job e política de retry.
- Retry não pode gerar pacotes duplicados ou sobrescrever exportação válida sem regra explícita.

## Testes
Use fixtures pequenas e determinísticas. Teste variações, seed, ordenação, gabarito, PDF com campos, conversão, ZIP, concorrência, timeout, falha intermediária, limpeza e isolamento entre tenants.
