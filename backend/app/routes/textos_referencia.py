from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app import secure_files
from backend.app.db_models import TextoReferenciaGeral
from backend.app.models import TextoReferenciaOut
from backend.app.security import get_tenant_db
from backend.app.utils_crypto import encrypt_text, decrypt_text
from backend.app.utils_vinculo import sincronizar_vinculo_texto_questao
from backend.app.security import evento_autorizado
import uuid, os, shutil, json, random, string
from datetime import datetime
from cryptography.fernet import InvalidToken

router = APIRouter()

def safe_decrypt(text):
    if not text:
        return None
    try:
        return decrypt_text(text)
    except InvalidToken:
        return text

def gerar_codigo_ref():
    letras = ''.join(random.choices(string.ascii_uppercase, k=2))
    numeros = ''.join(random.choices(string.digits, k=3))
    return f"TR-{letras}{numeros}"

@router.get(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/textos-referencia",
    response_model=list[TextoReferenciaOut],
    summary="Listar textos de referência por evento e conteúdo"
)
async def listar_textos_referencia(
    evento_id: str,
    conteudo_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado)
):
    result = await db.execute(
        select(TextoReferenciaGeral)
        .where(
            TextoReferenciaGeral.id_evento_fk == evento_id,
            TextoReferenciaGeral.id_conteudo_fk == conteudo_id
        )
        .order_by(TextoReferenciaGeral.data_criacao.desc())
    )
    textos = result.scalars().all()
    return [
        TextoReferenciaOut(
            id_texto_ref=tr.id_texto_ref,
            titulo=safe_decrypt(tr.titulo),
            conteudo=safe_decrypt(tr.conteudo),
            tipo_conteudo=tr.tipo_conteudo or "",
            codigo_ref=tr.codigo_ref,
            legenda_texto=safe_decrypt(tr.legenda_texto),
            descricao_imagem=getattr(tr, "descricao_imagem", None),
            fonte_imagem=getattr(tr, "fonte_imagem", None),
            tags_imagem=(tr.tags_imagem.split(",") if tr.tags_imagem else []),
            licenca_imagem=getattr(tr, "licenca_imagem", None),
            caminho_imagem_relativo=getattr(tr, "caminho_imagem_relativo", None),
            observacoes=getattr(tr, "observacoes", None),
            ativo=getattr(tr, "ativo", True),
            publico=getattr(tr, "publico", True),
            metadados_texto_ref=(json.loads(tr.metadados_texto_ref) if tr.metadados_texto_ref else None),
            questoes_vinculo=(tr.questoes_vinculo.split(",") if tr.questoes_vinculo else []),
            evento_id=tr.id_evento_fk,
            conteudo_id=tr.id_conteudo_fk,
            tenant_id=tr.tenant_id,
            conteudo_formatado=tr.conteudo_formatado
        )
        for tr in textos
    ]

@router.get(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/textos-referencia/{id_texto_ref}",
    response_model=TextoReferenciaOut,
    summary="Obter um texto de referência pelo ID"
)
async def get_texto_referencia(
    evento_id: str,
    conteudo_id: str,
    id_texto_ref: str,
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado)
):
    result = await db.execute(
        select(TextoReferenciaGeral)
        .where(
            TextoReferenciaGeral.id_texto_ref == id_texto_ref,
            TextoReferenciaGeral.id_evento_fk == evento_id,
            TextoReferenciaGeral.id_conteudo_fk == conteudo_id
        )
    )
    texto = result.scalars().first()
    if not texto:
        raise HTTPException(status_code=404, detail="Texto de referência não encontrado.")
    return TextoReferenciaOut(
        id_texto_ref=texto.id_texto_ref,
        titulo=safe_decrypt(texto.titulo),
        conteudo=safe_decrypt(texto.conteudo),
        tipo_conteudo=texto.tipo_conteudo,
        codigo_ref=texto.codigo_ref,
        legenda_texto=safe_decrypt(texto.legenda_texto),
        descricao_imagem=getattr(texto, "descricao_imagem", None),
        fonte_imagem=getattr(texto, "fonte_imagem", None),
        tags_imagem=(texto.tags_imagem.split(",") if texto.tags_imagem else []),
        licenca_imagem=getattr(texto, "licenca_imagem", None),
        caminho_imagem_relativo=getattr(texto, "caminho_imagem_relativo", None),
        observacoes=getattr(texto, "observacoes", None),
        ativo=getattr(texto, "ativo", True),
        publico=getattr(texto, "publico", True),
        metadados_texto_ref=(json.loads(texto.metadados_texto_ref) if texto.metadados_texto_ref else None),
        questoes_vinculo=(texto.questoes_vinculo.split(",") if texto.questoes_vinculo else []),
        evento_id=texto.id_evento_fk,
        conteudo_id=texto.id_conteudo_fk,
        tenant_id=texto.tenant_id,
        conteudo_formatado=texto.conteudo_formatado
    )

@router.post(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/textos-referencia",
    response_model=TextoReferenciaOut,
    summary="Criar um novo texto de referência"
)
async def criar_texto_referencia(
    evento_id: str,
    conteudo_id: str,
    titulo: str = Form(None),
    conteudo: str = Form(None),
    tipo_conteudo: str = Form(...),
    codigo_ref: str = Form(None),
    legenda_texto: str = Form(None),
    descricao_imagem: str = Form(None),
    fonte_imagem: str = Form(None),
    tags_imagem: str = Form(None),
    licenca_imagem: str = Form(None),
    observacoes: str = Form(None),
    ativo: bool = Form(True),
    publico: bool = Form(True),
    metadados_texto_ref: str = Form(None),
    questoes_vinculo: str = Form(None),
    tenant_id: int | None = Form(None),  # ignorado: o tenant vem do evento autorizado
    conteudo_formatado: str = Form(None),
    imagem: UploadFile = File(None),
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado)
):
    tags_list = tags_imagem.split(",") if tags_imagem else []
    questoes_list = questoes_vinculo.split(",") if questoes_vinculo else []
    metadados_dict = None
    if metadados_texto_ref:
        try:
            metadados_dict = json.loads(metadados_texto_ref)
        except Exception:
            raise HTTPException(status_code=400, detail="metadados_texto_ref deve ser JSON válido")

    caminho_imagem_relativo = None
    if imagem:
        caminho_imagem_relativo = await secure_files.save_upload_http(imagem, evento.tenant_id, "image")

    titulo_criptografado = encrypt_text(titulo) if titulo else None
    conteudo_criptografado = encrypt_text(conteudo) if conteudo else None
    legenda_texto_criptografada = encrypt_text(legenda_texto) if legenda_texto else None

    codigo_ref_value = codigo_ref or gerar_codigo_ref()

    novo = TextoReferenciaGeral(
        id_texto_ref=str(uuid.uuid4()),
        id_evento_fk=evento_id,
        id_conteudo_fk=conteudo_id,
        codigo_ref=codigo_ref_value,
        titulo=titulo_criptografado,
        conteudo=conteudo_criptografado,
        tipo_conteudo=tipo_conteudo,
        legenda_texto=legenda_texto_criptografada,
        descricao_imagem=descricao_imagem,
        fonte_imagem=fonte_imagem,
        tags_imagem=",".join(tags_list),
        licenca_imagem=licenca_imagem,
        caminho_imagem_relativo=caminho_imagem_relativo,
        observacoes=observacoes,
        ativo=ativo,
        publico=publico,
        metadados_texto_ref=json.dumps(metadados_dict) if metadados_dict else None,
        questoes_vinculo=",".join(questoes_list),
        conteudo_formatado=conteudo_formatado,
        data_criacao=str(datetime.now()),
        data_modificacao=str(datetime.now()),
        tenant_id=evento.tenant_id
    )
    db.add(novo)
    await db.commit()
    await db.refresh(novo)
    return TextoReferenciaOut(
        id_texto_ref=novo.id_texto_ref,
        titulo=safe_decrypt(novo.titulo),
        conteudo=safe_decrypt(novo.conteudo),
        tipo_conteudo=novo.tipo_conteudo,
        codigo_ref=novo.codigo_ref,
        legenda_texto=safe_decrypt(novo.legenda_texto),
        descricao_imagem=novo.descricao_imagem,
        fonte_imagem=novo.fonte_imagem,
        tags_imagem=(novo.tags_imagem.split(",") if novo.tags_imagem else []),
        licenca_imagem=novo.licenca_imagem,
        caminho_imagem_relativo=novo.caminho_imagem_relativo,
        observacoes=novo.observacoes,
        ativo=novo.ativo,
        publico=novo.publico,
        metadados_texto_ref=(json.loads(novo.metadados_texto_ref) if novo.metadados_texto_ref else None),
        questoes_vinculo=(novo.questoes_vinculo.split(",") if novo.questoes_vinculo else []),
        evento_id=novo.id_evento_fk,
        conteudo_id=novo.id_conteudo_fk,
        tenant_id=novo.tenant_id,
        conteudo_formatado=novo.conteudo_formatado
    )

# NOVO ENDPOINT PATCH PARA ATUALIZAR TEXTO DE REFERÊNCIA
@router.patch(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/textos-referencia/{id_texto_ref}",
    response_model=TextoReferenciaOut,
    summary="Atualizar um texto de referência"
)
async def atualizar_texto_referencia(
    evento_id: str,
    conteudo_id: str,
    id_texto_ref: str,
    titulo: str = Form(None),
    conteudo: str = Form(None),
    tipo_conteudo: str = Form(None),
    codigo_ref: str = Form(None),
    legenda_texto: str = Form(None),
    descricao_imagem: str = Form(None),
    fonte_imagem: str = Form(None),
    tags_imagem: str = Form(None),
    licenca_imagem: str = Form(None),
    observacoes: str = Form(None),
    ativo: bool = Form(None),
    publico: bool = Form(None),
    metadados_texto_ref: str = Form(None),
    questoes_vinculo: str = Form(None),
    tenant_id: int | None = Form(None),  # ignorado: o tenant do texto não pode ser alterado
    conteudo_formatado: str = Form(None),
    imagem: UploadFile = File(None),
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado)
):
    result = await db.execute(
        select(TextoReferenciaGeral)
        .where(
            TextoReferenciaGeral.id_texto_ref == id_texto_ref,
            TextoReferenciaGeral.id_evento_fk == evento_id,
            TextoReferenciaGeral.id_conteudo_fk == conteudo_id
        )
    )
    texto = result.scalars().first()
    if not texto:
        raise HTTPException(status_code=404, detail="Texto de referência não encontrado.")

    # Atualize os campos recebidos
    if titulo is not None:
        texto.titulo = encrypt_text(titulo)
    if conteudo is not None:
        texto.conteudo = encrypt_text(conteudo)
    if tipo_conteudo is not None:
        texto.tipo_conteudo = tipo_conteudo
    if codigo_ref is not None:
        texto.codigo_ref = codigo_ref
    if legenda_texto is not None:
        texto.legenda_texto = encrypt_text(legenda_texto)
    if descricao_imagem is not None:
        texto.descricao_imagem = descricao_imagem
    if fonte_imagem is not None:
        texto.fonte_imagem = fonte_imagem
    if tags_imagem is not None:
        texto.tags_imagem = tags_imagem
    if licenca_imagem is not None:
        texto.licenca_imagem = licenca_imagem
    if observacoes is not None:
        texto.observacoes = observacoes
    if ativo is not None:
        texto.ativo = ativo
    if publico is not None:
        texto.publico = publico
    if metadados_texto_ref is not None:
        try:
            texto.metadados_texto_ref = json.dumps(json.loads(metadados_texto_ref))
        except Exception:
            raise HTTPException(status_code=400, detail="metadados_texto_ref deve ser JSON válido")
    if questoes_vinculo is not None:
        texto.questoes_vinculo = questoes_vinculo
        lista_ids_questao = [q for q in questoes_vinculo.split(",") if q]
        await sincronizar_vinculo_texto_questao(db, id_texto_ref, lista_ids_questao)
    if conteudo_formatado is not None:
        texto.conteudo_formatado = conteudo_formatado

    # Atualizar imagem se enviada
    if imagem is not None:
        texto.caminho_imagem_relativo = await secure_files.save_upload_http(imagem, evento.tenant_id, "image")

    texto.data_modificacao = str(datetime.now())
    await db.commit()
    await db.refresh(texto)
    return TextoReferenciaOut(
        id_texto_ref=texto.id_texto_ref,
        titulo=safe_decrypt(texto.titulo),
        conteudo=safe_decrypt(texto.conteudo),
        tipo_conteudo=texto.tipo_conteudo,
        codigo_ref=texto.codigo_ref,
        legenda_texto=safe_decrypt(texto.legenda_texto),
        descricao_imagem=texto.descricao_imagem,
        fonte_imagem=texto.fonte_imagem,
        tags_imagem=(texto.tags_imagem.split(",") if texto.tags_imagem else []),
        licenca_imagem=texto.licenca_imagem,
        caminho_imagem_relativo=texto.caminho_imagem_relativo,
        observacoes=texto.observacoes,
        ativo=texto.ativo,
        publico=texto.publico,
        metadados_texto_ref=(json.loads(texto.metadados_texto_ref) if texto.metadados_texto_ref else None),
        questoes_vinculo=(texto.questoes_vinculo.split(",") if texto.questoes_vinculo else []),
        evento_id=texto.id_evento_fk,
        conteudo_id=texto.id_conteudo_fk,
        tenant_id=texto.tenant_id,
        conteudo_formatado=texto.conteudo_formatado
    )

@router.delete(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/textos-referencia/{id_texto_ref}",
    summary="Deletar um texto de referência"
)
async def deletar_texto_referencia(
    evento_id: str,
    conteudo_id: str,
    id_texto_ref: str,
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado)
):
    result = await db.execute(
        select(TextoReferenciaGeral)
        .where(
            TextoReferenciaGeral.id_texto_ref == id_texto_ref,
            TextoReferenciaGeral.id_evento_fk == evento_id,
            TextoReferenciaGeral.id_conteudo_fk == conteudo_id
        )
    )
    texto = result.scalars().first()
    if not texto:
        raise HTTPException(status_code=404, detail="Texto de referência não encontrado.")
    await db.delete(texto)
    await db.commit()
    return {"detail": "Texto de referência deletado com sucesso."}