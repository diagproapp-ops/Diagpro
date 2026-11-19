# core/instrucoes_padrao.py
"""
Textos padrão das instruções impressas na prova. A banca pode editar em Configurações > Identidade da prova;
enquanto não editar, a prova sai com estes textos (iguais aos que estavam fixos no gerador).
"""

# Instruções impressas no início de cada bloco cujo título contém a palavra indicada (sem diferenciar maiúsculas).
INSTRUCOES_POR_BLOCO = [
    {"contem": "informática", "instrucoes": ['Nas questões que abordarem conteúdos de informática e/ou tecnologia da informação, presume-se que todos os programas citados estão configurados em seus padrões originais, sem quaisquer limitações de acesso, funcionamento ou uso em relação aos softwares, arquivos, pastas, recursos e dispositivos mencionados.']},
]

# Instruções da seção Discursiva.
INSTRUCOES_DISCURSIVA = ['Nesta prova, faça o que se pede, usando, caso deseje, o espaço para rascunho indicado no presente caderno. Em seguida, transcreva o texto para o respectivo Caderno de Texto Definitivo, no local apropriado, pois não serão avaliados fragmentos de texto escritos em locais indevidos. A resposta deverá conter a extensão mínima e máxima de linhas para o texto conforme o edital.', 'Qualquer fragmento de texto que ultrapassar a extensão máxima de linhas será desconsiderado. Também será desconsiderado o texto que não for escrito no Caderno de Texto Definitivo.', 'O texto deverá ser manuscrito, em letra legível, com caneta esferográfica de tinta azul ou preta, fabricada com material transparente.', 'Será admitida a assinatura apenas no campo apropriado.', 'O Caderno de Texto Definitivo será o único documento válido para avaliação da prova discursiva.']
