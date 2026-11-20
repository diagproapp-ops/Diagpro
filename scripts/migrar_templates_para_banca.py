"""
Move os templates de prova das pastas dos EVENTOS para a BIBLIOTECA DA BANCA (Configurações > Templates de prova).

    python scripts/migrar_templates_para_banca.py            # só simula e mostra o que faria
    python scripts/migrar_templates_para_banca.py --aplicar  # migra de verdade

Para cada template: copia para a biblioteca (mesmo conteúdo, mesma data/autor do envio), confere byte a byte, guarda
os arquivos originais (continuam cifrados) em %LOCALAPPDATA%/DiagPro/backups/templates_eventos_<data>/ e só então os
remove da pasta do evento. Nome repetido com conteúdo diferente vira "Nome (EVENTO).docx". Se o evento ainda não
tem template padrão e tinha um único template, ele vira o padrão do evento.
"""
import argparse
import asyncio
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")
from sqlalchemy import select  # noqa: E402

from backend.app import secure_files  # noqa: E402
from backend.app.database import PlatformSessionLocal  # noqa: E402
from backend.app.db_models import Evento  # noqa: E402


def _pasta_backup() -> Path:
    base = Path(os.getenv("LOCALAPPDATA") or Path.home()) / "DiagPro" / "backups"
    return base / f"templates_eventos_{datetime.now():%Y%m%d-%H%M%S}"


async def main(aplicar: bool) -> int:
    raiz = Path(secure_files.TEMPLATES_ROOT)
    pastas = [p for p in raiz.iterdir() if p.is_dir() and not p.name.startswith("banca-")] if raiz.is_dir() else []
    if not pastas:
        print("Nada a migrar: nenhum evento com templates.")
        return 0
    backup = _pasta_backup()
    async with PlatformSessionLocal() as s:
        for pasta in pastas:
            evento = (await s.execute(select(Evento).where(Evento.id_evento == pasta.name))).scalar_one_or_none()
            if evento is None:
                print(f"[!] Pasta {pasta.name}: evento não encontrado no banco — deixada como está.")
                continue
            tenant, ident = evento.tenant_id, evento.identificador_evento or pasta.name[:8]
            dono = secure_files.dono_banca(tenant)
            nomes = secure_files.list_templates(pasta.name)
            print(f"Evento {ident} ({evento.nome_evento}) — banca {tenant}: {len(nomes)} template(s)")
            migrados = []
            for nome in nomes:
                dados = secure_files.read_template(pasta.name, nome, tenant)
                info = secure_files.info_template(pasta.name, nome, tenant)
                destino = nome
                if secure_files._template_path(dono, destino).is_file():
                    if secure_files.read_template(dono, destino, tenant) == dados:
                        print(f"    = {nome}: já está na biblioteca (idêntico)")
                        migrados.append((nome, destino))
                        continue
                    base, ext = os.path.splitext(nome)
                    destino = f"{base} ({ident}){ext}"
                print(f"    → {nome}  ⇒  biblioteca/{destino}")
                if aplicar:
                    secure_files.write_template(dono, destino, dados, tenant, enviado_por_id=info.get("enviado_por_id"),
                                                enviado_em=info.get("enviado_em"))
                    if secure_files.read_template(dono, destino, tenant) != dados:
                        raise SystemExit(f"Conferência falhou para {nome}: nada foi apagado.")
                migrados.append((nome, destino))
            prefs = dict(evento.preferencias_exportacao or {})
            atual = prefs.get("template")
            renomes = dict(migrados)
            if atual in renomes and renomes[atual] != atual:
                prefs["template"] = renomes[atual]
                print(f"    padrão do evento: {atual} ⇒ {renomes[atual]}")
            elif not atual and len(migrados) == 1:
                prefs["template"] = migrados[0][1]
                print(f"    padrão do evento: {migrados[0][1]} (era o único template)")
            else:
                print(f"    padrão do evento: {atual or '(nenhum — escolha na tela do evento)'}")
            if aplicar:
                evento.preferencias_exportacao = prefs
                await s.commit()
                destino_backup = backup / pasta.name
                destino_backup.mkdir(parents=True, exist_ok=True)
                for arq in pasta.iterdir():
                    shutil.copy2(arq, destino_backup / arq.name)
                for nome, _ in migrados:
                    secure_files.delete_template(pasta.name, nome)
                if not any(pasta.iterdir()):
                    pasta.rmdir()
                print(f"    originais guardados (cifrados) em {destino_backup}")
    if not aplicar:
        print("\nSimulação: nada foi alterado. Rode com --aplicar para migrar.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args().aplicar)))
