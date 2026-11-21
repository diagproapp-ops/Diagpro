CAMPOS_CAPA_PROVA = [
    # Dados do candidato
    "Inscricao",
    "NomeCandidato",
    "CPF",
    "RG",
    "DataNascimento",
    "Sexo",
    "FotoCandidato",
    "Telefone",
    "Email",
    "Escola",
    "Curso",
    "Modalidade",
    "Sala",
    "Bloco",
    "Turno",
    "Periodo",
    "NumeroOrdemGeral",
    "NumeroOrdemSala",

    # Prova/Cargo
    "CodigoCargo",
    "NomeCargo",
    "CargoTipo",
    "CargoTipoCompleto",
    "CargoCompleto",
    "Tipo",
    "letra_tipo",
    "NomeProva",
    "IdentificadorProva",
    "TipoProva",
    "QuantidadeQuestoes",
    "TempoProva",
    "NumeroProva",

    # Evento
    "NomeEvento",
    "DataEvento",
    "LocalEvento",
    "DataProva",

    # Empresa/Banca
    "Empresa",
    "EnderecoEmpresa",

    # Frase motivacional
    "Frase",

    # QRCode
    "QRCode",

    # Assinaturas/Observações
    "AssinaturaCandidato",
    "AssinaturaFiscal",
    "Observacoes",

    # Extras
    "Outros"
]

def montar_dados_capa(
    candidato,
    cargo,
    evento,
    prova,
    frase,
    tipo,
    tempo_prova,
    quantidade_questoes,
    empresa,
    qrcode="",
    outros="",
    letra_tipo=None,
):
    def data(valor):
        return valor.strftime("%d/%m/%Y") if hasattr(valor, "strftime") else (str(valor) if valor else "")

    nome_cargo, codigo_cargo = getattr(cargo, "nome_cargo", "") or "", getattr(cargo, "codigo_cargo", "") or ""
    data_prova = data(getattr(evento, "data_prova", None))
    letra = letra_tipo if letra_tipo is not None else ""
    dados = {
        "Inscricao": candidato.get("inscricao", ""),
        "NomeCandidato": candidato.get("nome", ""),
        "CPF": candidato.get("cpf", ""),
        "RG": candidato.get("rg", ""),
        "DataNascimento": candidato.get("data_nascimento", ""),
        "Sexo": candidato.get("sexo", ""),
        "FotoCandidato": candidato.get("foto", ""),
        "Telefone": candidato.get("telefone", ""),
        "Email": candidato.get("email", ""),
        "Escola": candidato.get("escola", ""),
        "Curso": candidato.get("curso", ""),
        "Modalidade": candidato.get("modalidade", ""),
        "Sala": candidato.get("sala", ""),
        "Bloco": candidato.get("bloco", ""),
        "Turno": candidato.get("turno", "") or (getattr(cargo, "turno", "") or ""),
        "Periodo": candidato.get("periodo", ""),
        "NumeroOrdemGeral": candidato.get("ordem_geral", ""),
        "NumeroOrdemSala": candidato.get("ordem_sala", ""),
        "CodigoCargo": codigo_cargo,
        "NomeCargo": nome_cargo,
        "NivelCargo": getattr(cargo, "nivel", "") or "",
        "CargoTipo": f"{nome_cargo} ({tipo})",
        "CargoTipoCompleto": f"{codigo_cargo} - {nome_cargo} - {tipo}",
        "CargoCompleto": f"{codigo_cargo} - {nome_cargo}",
        "Tipo": tipo,
        "LetraTipo": letra,
        "letra_tipo": letra,  # nome antigo, mantido para capas já feitas
        "NomeProva": getattr(prova, "nome_prova_montada", "") or getattr(prova, "nome_prova", "") or "",
        "IdentificadorProva": tipo,
        "TipoProva": tipo,
        "QuantidadeQuestoes": quantidade_questoes,
        "TempoProva": tempo_prova,
        "NumeroProva": getattr(prova, "numero_prova", "") or "",
        "NomeEvento": getattr(evento, "nome_evento", "") or "",
        "NumeroEdital": getattr(evento, "numero_edital", "") or "",
        "DataEvento": data_prova,
        "LocalEvento": getattr(evento, "local_prova", "") or "",
        "DataProva": data_prova,
        "Empresa": empresa,
        "EnderecoEmpresa": getattr(evento, "endereco_empresa", "") or "",
        "Frase": frase,
        "QRCode": qrcode,
        "AssinaturaCandidato": "",
        "AssinaturaFiscal": "",
        "Observacoes": "",
        "Outros": outros,
    }
    return {k: ("" if v is None else str(v)) for k, v in dados.items()}


# Guia dos campos para quem monta o PDF de capa: o campo de formulário do PDF precisa ter EXATAMENTE este nome.
# origem: "automatico" = o DiagPro preenche; "em_branco" = fica em branco (para preencher à mão ou pela gráfica).
GUIA_CAMPOS = [
    # grupo, campo, descrição, exemplo, origem
    ("Evento", "NomeEvento", "Nome do concurso/evento", "Concurso Público 2026", "automatico"),
    ("Evento", "NumeroEdital", "Número do edital", "01/2026", "automatico"),
    ("Evento", "DataProva", "Data da prova (dd/mm/aaaa)", "14/12/2026", "automatico"),
    ("Evento", "DataEvento", "Mesmo que DataProva", "14/12/2026", "automatico"),
    ("Evento", "LocalEvento", "Local da prova cadastrado no evento", "Escola Estadual Centro", "automatico"),
    ("Cargo", "NomeCargo", "Nome do cargo", "Analista de TI", "automatico"),
    ("Cargo", "CodigoCargo", "Código do cargo", "AN-01", "automatico"),
    ("Cargo", "NivelCargo", "Nível do cargo", "Nível Superior", "automatico"),
    ("Cargo", "CargoCompleto", "Código - Nome do cargo", "AN-01 - Analista de TI", "automatico"),
    ("Cargo", "CargoTipo", "Nome do cargo (tipo da prova)", "Analista de TI (Tipo A)", "automatico"),
    ("Cargo", "CargoTipoCompleto", "Código - Nome - Tipo", "AN-01 - Analista de TI - Tipo A", "automatico"),
    ("Cargo", "Turno", "Turno do cargo", "Tarde", "automatico"),
    ("Prova", "Tipo", "Tipo da prova (PADRÃO ou Tipo A, B...)", "Tipo A", "automatico"),
    ("Prova", "LetraTipo", "Só a letra do tipo (vazio na prova PADRÃO)", "A", "automatico"),
    ("Prova", "TipoProva", "Mesmo que Tipo", "Tipo A", "automatico"),
    ("Prova", "IdentificadorProva", "Mesmo que Tipo", "Tipo A", "automatico"),
    ("Prova", "NomeProva", "Nome da prova montada", "Prova Objetiva", "automatico"),
    ("Prova", "QuantidadeQuestoes", "Total de questões da prova", "60", "automatico"),
    ("Prova", "Frase", "Frase para transcrição (banco de frases da geração)", "A persistência realiza o impossível.", "automatico"),
    ("Banca", "Empresa", "Nome da banca (Dados da banca)", "Minha Banca", "automatico"),
    ("Prova", "TempoProva", "Duração da prova", "4 horas", "em_branco"),
    ("Prova", "NumeroProva", "Número da prova", "", "em_branco"),
    ("Banca", "EnderecoEmpresa", "Endereço da banca", "", "em_branco"),
    ("Candidato", "NomeCandidato", "Nome do candidato", "", "em_branco"),
    ("Candidato", "Inscricao", "Número de inscrição", "", "em_branco"),
    ("Candidato", "CPF", "CPF do candidato", "", "em_branco"),
    ("Candidato", "RG", "RG do candidato", "", "em_branco"),
    ("Candidato", "DataNascimento", "Data de nascimento", "", "em_branco"),
    ("Candidato", "Sala", "Sala", "", "em_branco"),
    ("Candidato", "Bloco", "Bloco", "", "em_branco"),
    ("Candidato", "NumeroOrdemSala", "Número de ordem na sala", "", "em_branco"),
    ("Candidato", "NumeroOrdemGeral", "Número de ordem geral", "", "em_branco"),
    ("Assinaturas", "AssinaturaCandidato", "Espaço para assinatura do candidato", "", "em_branco"),
    ("Assinaturas", "AssinaturaFiscal", "Espaço para assinatura do fiscal", "", "em_branco"),
    ("Assinaturas", "Observacoes", "Observações", "", "em_branco"),
    ("Outros", "QRCode", "Reservado para QR Code", "", "em_branco"),
    ("Outros", "Outros", "Campo livre", "", "em_branco"),
]
CAMPOS_RECONHECIDOS = {c[1] for c in GUIA_CAMPOS} | set(CAMPOS_CAPA_PROVA) | {"letra_tipo", "LetraTipo"}


def guia() -> list[dict]:
    return [{"grupo": g, "campo": c, "descricao": d, "exemplo": e, "origem": o} for g, c, d, e, o in GUIA_CAMPOS]
