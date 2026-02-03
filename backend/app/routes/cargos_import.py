from fastapi import APIRouter, UploadFile, File, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.database import get_db
from backend.app.db_models import Cargo as DBCargo, DisciplinaDaProva as DBDisciplinaDaProva, Disciplina as DBDisciplina
from backend.app.auth import get_current_user
import csv
import uuid
from io import StringIO

router = APIRouter()

# Função global única!
async def gerar_identificador_cargo_global(nome_cargo: str, db: AsyncSession, usados: set):
    letras = ''.join([c for c in nome_cargo if c.isalpha()]).upper()[:2]
    if len(letras) < 2:
        letras = letras.ljust(2, 'X')
    prefix = f"{letras}"
    result = await db.execute(
        select(DBCargo.identificador_cargo)
        .filter(DBCargo.identificador_cargo.like(f"{prefix}%"))
    )
    existentes = set(result.scalars().all())
    usados = usados | existentes  # Unifica os já usados nesta importação com os do banco
    max_num = 0
    for ident in usados:
        if ident and ident.startswith(prefix):
            try:
                num = int(ident[len(prefix):])
                if num > max_num:
                    max_num = num
            except Exception:
                continue
    while True:
        numero = str(max_num + 1).zfill(3)
        novo_ident = f"{prefix}{numero}"
        if novo_ident not in usados:
            return novo_ident
        max_num += 1

@router.post("/eventos/{event_id}/cargos/import-csv", status_code=status.HTTP_201_CREATED)
async def import_cargos_csv(
    event_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    content = await file.read()
    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            csv_text = content.decode("latin1")
        except UnicodeDecodeError:
            csv_text = content.decode("cp1252")

    reader = csv.DictReader(StringIO(csv_text), delimiter=";")
    cargos_importados = 0
    erros = []

    # Set para registrar todos os identificadores reservados nesta importação
    identificadores_usados = set()

    for idx, row in enumerate(reader, start=1):
        try:
            nome_cargo = row.get("nome_cargo", "").strip()
            if not nome_cargo:
                erros.append(f"Linha {idx}: nome_cargo vazio. Linha ignorada.")
                continue
            identificador_cargo = await gerar_identificador_cargo_global(nome_cargo, db, identificadores_usados)
            identificadores_usados.add(identificador_cargo)

            cargo_id = str(uuid.uuid4())
            db_cargo = DBCargo(
                id_cargo=cargo_id,
                identificador_cargo=identificador_cargo,
                tenant_id=current_user.tenant_id,
                id_evento_fk=event_id,
                codigo_cargo=row.get("codigo_cargo"),
                nome_cargo=nome_cargo,
                nivel=row.get("nivel"),
                turno=row.get("turno"),
                vagas=int(row.get("vagas") or 0),
                salario=float(row.get("salario") or 0),
                requisitos=row.get("requisitos"),
                tem_discursiva=row.get("tem_discursiva") in ["1", "True", "true", "SIM", "sim", "Sim"],
                peso_total_prova=float(row.get("peso_total_prova") or 0),
            )
            db.add(db_cargo)

            i = 1
            while True:
                header_nome = f'disciplina_{i}'
                if header_nome not in row:
                    break
                nome_disciplina = row.get(header_nome, '').strip()
                if not nome_disciplina:
                    i += 1
                    continue
                try:
                    qtd_questoes = int(row.get(f'qtd_questoes_{i}', '0') or '0')
                except Exception:
                    qtd_questoes = 0
                try:
                    peso = float(row.get(f'peso_{i}', '0') or '0')
                except Exception:
                    peso = 0.0
                obs = row.get(f'obs_{i}', '').strip() or None
                try:
                    ordem = int(row.get(f'ordem_{i}', str(i)) or str(i))
                except Exception:
                    ordem = i
                tipo_col = row.get(f"tipo_conhecimento_{i}", "comum").strip().lower()
                if tipo_col not in ("comum", "basico", "especifico"):
                    tipo_col = "comum"

                result_disc = await db.execute(
                    select(DBDisciplina).where(
                        DBDisciplina.nome_disciplina == nome_disciplina,
                        DBDisciplina.id_evento_fk == event_id
                    )
                )
                db_disc = result_disc.scalar_one_or_none()
                if db_disc:
                    id_disciplina_base_fk = db_disc.id_disciplina
                else:
                    id_disciplina_base_fk = str(uuid.uuid4())
                    db_disc_new = DBDisciplina(
                        id_disciplina=id_disciplina_base_fk,
                        id_evento_fk=event_id,
                        nome_disciplina=nome_disciplina,
                        # Adicione tenant_id se existir no modelo Disciplina
                    )
                    db.add(db_disc_new)
                    await db.commit()

                db_disciplina_prova = DBDisciplinaDaProva(
                    id_disciplina_prova=str(uuid.uuid4()),
                    id_cargo_fk=cargo_id,
                    id_disciplina_base_fk=id_disciplina_base_fk,
                    nome_disciplina_na_prova=nome_disciplina,
                    qtd_questoes=qtd_questoes,
                    peso_por_questao=peso,
                    ordem_na_prova=ordem,
                    observacoes=obs,
                    tipo_conhecimento=tipo_col,
                    tenant_id=current_user.tenant_id,
                )
                db.add(db_disciplina_prova)
                i += 1

            cargos_importados += 1

        except Exception as e:
            erros.append(f"Linha {idx}: {e}")
            continue
    await db.commit()
    return {
        "importados": cargos_importados,
        "erros": erros
    }