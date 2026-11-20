/**
 * Modelos do criador de equações, por área. "#?" é a lacuna que o usuário preenche.
 * Todos são conferidos por tests/test_equacoes.py::test_every_palette_template_prints (cada um precisa sair na prova).
 * Ficaram de fora de propósito: \boxed e \cancel (o PDF da prova não desenha) e \ce (química: use \mathrm).
 */
export type ModeloEquacao = { latex: string; titulo: string };
export type CategoriaEquacao = { id: string; nome: string; modelos: ModeloEquacao[] };

const m = (latex: string, titulo: string): ModeloEquacao => ({ latex, titulo });
const simbolos = (lista: [string, string][]) => lista.map(([latex, titulo]) => m(latex, titulo));

export const CATEGORIAS_EQUACAO: CategoriaEquacao[] = [
  {
    id: 'basico', nome: 'Básico', modelos: [
      m('\\frac{#?}{#?}', 'Fração'), m('#?^{#?}', 'Potência'), m('#?_{#?}', 'Índice'), m('#?_{#?}^{#?}', 'Índice e potência'),
      m('\\sqrt{#?}', 'Raiz quadrada'), m('\\sqrt[#?]{#?}', 'Raiz de índice n'), m('\\left(#?\\right)', 'Parênteses'),
      m('\\left[#?\\right]', 'Colchetes'), m('\\left\\{#?\\right\\}', 'Chaves'), m('\\left|#?\\right|', 'Módulo'),
      m('#?\\cdot #?', 'Multiplicação (ponto)'), m('#?\\times #?', 'Multiplicação (×)'), m('#?\\div #?', 'Divisão (÷)'),
      m('\\pm', 'Mais ou menos'), m('\\mp', 'Menos ou mais'), m('#?^{\\circ}', 'Graus'), m('#?\\%', 'Porcentagem'),
      m('#?!', 'Fatorial'), m('\\text{#?}', 'Texto dentro da equação'),
    ],
  },
  {
    id: 'gregas', nome: 'Letras gregas', modelos: simbolos([
      ['\\alpha', 'alfa'], ['\\beta', 'beta'], ['\\gamma', 'gama'], ['\\delta', 'delta'], ['\\epsilon', 'épsilon'],
      ['\\varepsilon', 'épsilon (variante)'], ['\\zeta', 'zeta'], ['\\eta', 'eta'], ['\\theta', 'teta'], ['\\vartheta', 'teta (variante)'],
      ['\\iota', 'iota'], ['\\kappa', 'capa'], ['\\lambda', 'lambda'], ['\\mu', 'mi'], ['\\nu', 'ni'], ['\\xi', 'csi'],
      ['\\pi', 'pi'], ['\\rho', 'rô'], ['\\sigma', 'sigma'], ['\\tau', 'tau'], ['\\upsilon', 'ípsilon'], ['\\phi', 'fi'],
      ['\\varphi', 'fi (variante)'], ['\\chi', 'qui'], ['\\psi', 'psi'], ['\\omega', 'ômega'],
      ['\\Gamma', 'Gama'], ['\\Delta', 'Delta'], ['\\Theta', 'Teta'], ['\\Lambda', 'Lambda'], ['\\Xi', 'Csi'], ['\\Pi', 'Pi'],
      ['\\Sigma', 'Sigma'], ['\\Phi', 'Fi'], ['\\Psi', 'Psi'], ['\\Omega', 'Ômega'],
    ]),
  },
  {
    id: 'relacoes', nome: 'Operadores e relações', modelos: simbolos([
      ['=', 'igual'], ['\\neq', 'diferente'], ['\\approx', 'aproximadamente'], ['\\equiv', 'idêntico / congruente'],
      ['\\cong', 'congruente'], ['\\sim', 'semelhante'], ['\\propto', 'proporcional'], ['<', 'menor'], ['>', 'maior'],
      ['\\leq', 'menor ou igual'], ['\\geq', 'maior ou igual'], ['\\ll', 'muito menor'], ['\\gg', 'muito maior'],
      ['\\pm', 'mais ou menos'], ['\\times', 'vezes'], ['\\div', 'dividido'], ['\\cdot', 'ponto'], ['\\circ', 'composição'],
      ['\\infty', 'infinito'], ['\\partial', 'derivada parcial'], ['\\nabla', 'nabla'], ['\\therefore', 'portanto'],
      ['\\because', 'porque'], ['\\ldots', 'reticências'], ['\\cdots', 'reticências centradas'], ['\\vdots', 'reticências verticais'],
      ['\\ddots', 'reticências diagonais'], ['\\perp', 'perpendicular'], ['\\parallel', 'paralelo'],
    ]),
  },
  {
    id: 'setas', nome: 'Setas', modelos: simbolos([
      ['\\to', 'tende a'], ['\\rightarrow', 'seta à direita'], ['\\leftarrow', 'seta à esquerda'], ['\\leftrightarrow', 'seta dupla'],
      ['\\Rightarrow', 'implica'], ['\\Leftarrow', 'é implicado por'], ['\\Leftrightarrow', 'se e somente se'],
      ['\\uparrow', 'seta para cima'], ['\\downarrow', 'seta para baixo'], ['\\mapsto', 'leva em'],
      ['\\longrightarrow', 'seta longa'], ['\\rightleftharpoons', 'equilíbrio'], ['\\nearrow', 'seta nordeste'], ['\\searrow', 'seta sudeste'],
    ]),
  },
  {
    id: 'conjuntos', nome: 'Conjuntos e lógica', modelos: [
      ...simbolos([
        ['\\in', 'pertence'], ['\\notin', 'não pertence'], ['\\subset', 'contido'], ['\\supset', 'contém'],
        ['\\subseteq', 'contido ou igual'], ['\\supseteq', 'contém ou igual'], ['\\cup', 'união'], ['\\cap', 'interseção'],
        ['\\setminus', 'diferença'], ['\\emptyset', 'vazio'], ['\\varnothing', 'vazio (variante)'],
        ['\\mathbb{N}', 'naturais'], ['\\mathbb{Z}', 'inteiros'], ['\\mathbb{Q}', 'racionais'], ['\\mathbb{R}', 'reais'], ['\\mathbb{C}', 'complexos'],
        ['\\forall', 'para todo'], ['\\exists', 'existe'], ['\\nexists', 'não existe'], ['\\neg', 'não'], ['\\land', 'e'],
        ['\\lor', 'ou'], ['\\Rightarrow', 'implica'], ['\\Leftrightarrow', 'bicondicional'], ['\\oplus', 'ou exclusivo'],
      ]),
      m('\\{#?\\mid #?\\}', 'Conjunto por propriedade'), m('\\{#?, #?\\}', 'Conjunto por elementos'), m('#?^{c}', 'Complementar'),
      m('[#?, #?]', 'Intervalo fechado'), m(']#?, #?[', 'Intervalo aberto'), m('[#?, #?)', 'Intervalo semiaberto'),
    ],
  },
  {
    id: 'calculo', nome: 'Cálculo', modelos: [
      m('\\lim_{#?\\to #?} #?', 'Limite'), m('\\lim_{x\\to\\infty} #?', 'Limite no infinito'), m('\\frac{d}{dx} #?', 'Derivada'),
      m('\\frac{d#?}{d#?}', 'Derivada (razão)'), m('\\frac{d^{2}#?}{d#?^{2}}', 'Segunda derivada'), m('\\frac{\\partial #?}{\\partial #?}', 'Derivada parcial'),
      m("#?'(#?)", 'Linha (derivada)'), m("#?''(#?)", 'Duas linhas'), m('\\int #?\\,dx', 'Integral indefinida'),
      m('\\int_{#?}^{#?} #?\\,dx', 'Integral definida'), m('\\iint_{#?} #?\\,dA', 'Integral dupla'), m('\\iiint_{#?} #?\\,dV', 'Integral tripla'),
      m('\\oint_{#?} #?', 'Integral de contorno'), m('\\left. #?\\right|_{#?}^{#?}', 'Avaliado de a até b'), m('\\nabla #?', 'Gradiente'),
      m('\\Delta #?', 'Variação'), m('e^{#?}', 'Exponencial'),
    ],
  },
  {
    id: 'somas', nome: 'Somatórios e produtos', modelos: [
      m('\\sum_{#?}^{#?} #?', 'Somatório'), m('\\sum_{i=1}^{n} #?', 'Somatório de 1 a n'), m('\\sum #?', 'Somatório simples'),
      m('\\prod_{#?}^{#?} #?', 'Produtório'), m('\\bigcup_{#?}^{#?} #?', 'União de vários'), m('\\bigcap_{#?}^{#?} #?', 'Interseção de vários'),
    ],
  },
  {
    id: 'matrizes', nome: 'Matrizes e determinantes', modelos: [
      m('\\begin{pmatrix}#?&#?\\\\#?&#?\\end{pmatrix}', 'Matriz 2×2'),
      m('\\begin{pmatrix}#?&#?&#?\\\\#?&#?&#?\\\\#?&#?&#?\\end{pmatrix}', 'Matriz 3×3'),
      m('\\begin{bmatrix}#?&#?\\\\#?&#?\\end{bmatrix}', 'Matriz 2×2 com colchetes'),
      m('\\begin{bmatrix}#?&#?&#?\\\\#?&#?&#?\\\\#?&#?&#?\\end{bmatrix}', 'Matriz 3×3 com colchetes'),
      m('\\begin{vmatrix}#?&#?\\\\#?&#?\\end{vmatrix}', 'Determinante 2×2'),
      m('\\begin{vmatrix}#?&#?&#?\\\\#?&#?&#?\\\\#?&#?&#?\\end{vmatrix}', 'Determinante 3×3'),
      m('\\begin{pmatrix}#?\\\\#?\\\\#?\\end{pmatrix}', 'Matriz coluna'), m('\\begin{pmatrix}#?&#?&#?\\end{pmatrix}', 'Matriz linha'),
      m('\\begin{matrix}#?&#?\\\\#?&#?\\end{matrix}', 'Tabela sem delimitador'), m('#?^{T}', 'Transposta'), m('#?^{-1}', 'Inversa'),
      m('\\det(#?)', 'Determinante de'),
    ],
  },
  {
    id: 'sistemas', nome: 'Sistemas e alinhamentos', modelos: [
      m('\\begin{cases}#?\\\\#?\\end{cases}', 'Sistema de 2 equações'), m('\\begin{cases}#?\\\\#?\\\\#?\\end{cases}', 'Sistema de 3 equações'),
      m('\\begin{cases}#?, & \\text{se } #?\\\\#?, & \\text{se } #?\\end{cases}', 'Função por partes'),
      m('\\begin{aligned}#?&=#?\\\\#?&=#?\\end{aligned}', 'Equações alinhadas no ='),
    ],
  },
  {
    id: 'trigonometria', nome: 'Trigonometria', modelos: [
      m('\\sin #?', 'seno'), m('\\cos #?', 'cosseno'), m('\\tan #?', 'tangente'), m('\\cot #?', 'cotangente'), m('\\sec #?', 'secante'),
      m('\\csc #?', 'cossecante'), m('\\arcsin #?', 'arco seno'), m('\\arccos #?', 'arco cosseno'), m('\\arctan #?', 'arco tangente'),
      m('\\sin^{2} #?', 'seno ao quadrado'), m('\\sin^{2}\\theta+\\cos^{2}\\theta=1', 'Relação fundamental'),
      m('\\sin(a+b)=\\sin a\\cos b+\\sin b\\cos a', 'Seno da soma'), m('\\tan\\theta=\\frac{\\sin\\theta}{\\cos\\theta}', 'Tangente'),
    ],
  },
  {
    id: 'logaritmos', nome: 'Logaritmos e exponenciais', modelos: [
      m('\\log_{#?} #?', 'Logaritmo na base'), m('\\log #?', 'Logaritmo decimal'), m('\\ln #?', 'Logaritmo natural'), m('e^{#?}', 'Exponencial'),
      m('\\log_{a}(xy)=\\log_{a}x+\\log_{a}y', 'Log do produto'), m('\\log_{a}x^{n}=n\\log_{a}x', 'Log da potência'),
      m('a^{m}\\cdot a^{n}=a^{m+n}', 'Produto de potências'),
    ],
  },
  {
    id: 'geometria', nome: 'Geometria', modelos: [
      m('\\overline{#?}', 'Segmento'), m('\\overrightarrow{#?}', 'Vetor / semirreta'), m('\\angle #?', 'Ângulo'),
      m('\\triangle #?', 'Triângulo'), m('\\widehat{#?}', 'Ângulo (chapéu)'), m('#?^{\\circ}', 'Graus'), m('\\perp', 'Perpendicular'),
      m('\\parallel', 'Paralelo'), m('\\cong', 'Congruente'), m('\\sim', 'Semelhante'), m('A=\\pi r^{2}', 'Área do círculo'),
      m('C=2\\pi r', 'Comprimento da circunferência'), m('a^{2}=b^{2}+c^{2}', 'Pitágoras'),
    ],
  },
  {
    id: 'vetores', nome: 'Vetores', modelos: [
      m('\\vec{#?}', 'Vetor'), m('\\overrightarrow{#?}', 'Vetor (seta longa)'), m('\\hat{#?}', 'Versor'), m('\\|#?\\|', 'Norma'),
      m('#?\\cdot #?', 'Produto escalar'), m('#?\\times #?', 'Produto vetorial'), m('\\vec{i}', 'vetor i'), m('\\vec{j}', 'vetor j'), m('\\vec{k}', 'vetor k'),
    ],
  },
  {
    id: 'estatistica', nome: 'Estatística e probabilidade', modelos: [
      m('\\bar{#?}', 'Média (barra)'), m('\\bar{x}=\\frac{1}{n}\\sum_{i=1}^{n}x_{i}', 'Média aritmética'), m('\\sigma', 'Desvio padrão'),
      m('\\sigma^{2}', 'Variância'), m('\\sigma=\\sqrt{\\frac{\\sum(x_{i}-\\bar{x})^{2}}{n}}', 'Desvio padrão (fórmula)'), m('\\mu', 'Média populacional'),
      m('P(#?)', 'Probabilidade'), m('P(#?\\mid #?)', 'Probabilidade condicional'), m('\\binom{#?}{#?}', 'Combinação (binomial)'),
      m('C_{n,p}=\\frac{n!}{p!(n-p)!}', 'Combinação'), m('A_{n,p}=\\frac{n!}{(n-p)!}', 'Arranjo'), m('P_{n}=n!', 'Permutação'),
      m('E(X)', 'Esperança'), m('\\text{Var}(X)', 'Variância de X'),
    ],
  },
  {
    id: 'quimica', nome: 'Química', modelos: [
      m('\\mathrm{H_{2}O}', 'Água'), m('\\mathrm{CO_{2}}', 'Gás carbônico'), m('\\mathrm{#?}_{#?}', 'Elemento com índice'),
      m('\\mathrm{#?}^{#?}', 'Íon (carga)'), m('\\mathrm{Na^{+}}', 'Cátion sódio'), m('\\mathrm{SO_{4}^{2-}}', 'Íon sulfato'),
      m('\\rightarrow', 'Reação'), m('\\rightleftharpoons', 'Equilíbrio'), m('\\Delta H', 'Variação de entalpia'),
      m('\\text{(aq)}', 'aquoso'), m('\\text{(s)}', 'sólido'), m('\\text{(l)}', 'líquido'), m('\\text{(g)}', 'gasoso'),
      m('\\mathrm{2H_{2}+O_{2}\\rightarrow 2H_{2}O}', 'Reação (exemplo)'),
    ],
  },
  {
    id: 'fisica', nome: 'Física e unidades', modelos: [
      m('\\vec{F}=m\\vec{a}', '2ª lei de Newton'), m('E=mc^{2}', 'Massa-energia'), m('E_{c}=\\frac{mv^{2}}{2}', 'Energia cinética'),
      m('v=\\frac{\\Delta s}{\\Delta t}', 'Velocidade média'), m('U=R\\cdot i', 'Lei de Ohm'), m('\\Delta #?', 'Variação'),
      m('\\text{m/s}', 'm/s'), m('\\text{m/s}^{2}', 'm/s²'), m('\\text{km/h}', 'km/h'), m('\\text{N}', 'newton'), m('\\text{J}', 'joule'),
      m('\\text{W}', 'watt'), m('\\Omega', 'ohm'), m('^{\\circ}\\text{C}', 'grau Celsius'), m('\\mu\\text{m}', 'micrômetro'),
      m('\\lambda', 'comprimento de onda'), m('\\hbar', 'h cortado'),
    ],
  },
  {
    id: 'acentos', nome: 'Acentos e marcas', modelos: [
      m('\\hat{#?}', 'Chapéu'), m('\\bar{#?}', 'Barra'), m('\\tilde{#?}', 'Til'), m('\\dot{#?}', 'Ponto'), m('\\ddot{#?}', 'Dois pontos'),
      m('\\vec{#?}', 'Seta'), m('\\overline{#?}', 'Barra longa'), m('\\overbrace{#?}^{#?}', 'Chave em cima'),
      m('\\underbrace{#?}_{#?}', 'Chave embaixo'), m('#?\'', 'Linha'),
    ],
  },
  {
    id: 'prontas', nome: 'Fórmulas prontas', modelos: [
      m('x=\\frac{-b\\pm\\sqrt{b^{2}-4ac}}{2a}', 'Bhaskara'), m('\\Delta=b^{2}-4ac', 'Discriminante'),
      m('f(x)=ax^{2}+bx+c', 'Função quadrática'), m('y=mx+b', 'Reta (reduzida)'),
      m('d=\\sqrt{(x_{2}-x_{1})^{2}+(y_{2}-y_{1})^{2}}', 'Distância entre pontos'),
      m('a_{n}=a_{1}+(n-1)r', 'Termo geral da PA'), m('S_{n}=\\frac{(a_{1}+a_{n})n}{2}', 'Soma da PA'),
      m('a_{n}=a_{1}\\cdot q^{n-1}', 'Termo geral da PG'), m('S_{n}=\\frac{a_{1}(q^{n}-1)}{q-1}', 'Soma da PG'),
      m('M=C(1+i)^{t}', 'Juros compostos'), m('J=C\\cdot i\\cdot t', 'Juros simples'),
      m('\\frac{a}{\\sin A}=\\frac{b}{\\sin B}=\\frac{c}{\\sin C}', 'Lei dos senos'), m('a^{2}=b^{2}+c^{2}-2bc\\cos A', 'Lei dos cossenos'),
      m('(a+b)^{n}=\\sum_{k=0}^{n}\\binom{n}{k}a^{n-k}b^{k}', 'Binômio de Newton'), m('e^{i\\pi}+1=0', 'Identidade de Euler'),
      m('V=\\frac{4}{3}\\pi r^{3}', 'Volume da esfera'),
    ],
  },
];

/** Modelo para mostrar no botão (lacunas viram quadradinhos). */
export const paraVisualizar = (latex: string) =>
  latex.replace(/\\text\{#\?\}/g, '\\text{abc}').replace(/#\?/g, '\\square');
