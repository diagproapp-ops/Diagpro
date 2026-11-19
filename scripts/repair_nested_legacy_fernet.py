"""
Remove a camada de cifra LEGADA (Fernet) que ficou EMBUTIDA dentro de valores JSON/texto.

Contexto: antes da fase 1b, algumas rotas cifravam campo a campo com Fernet e guardavam o resultado
dentro de JSON (ex.: enunciados e alternativas na cópia da prova montada, palavras-chave de questões
discursivas). A conversão da fase 1b tratou o valor da coluna como um todo, então esses tokens internos
continuaram cifrados com a chave antiga e apareciam ilegíveis na prova diagramada.

O que faz, para cada coluna de field_crypto.ENCRYPTED (lida pelo ORM, já decifrada):
  1. percorre o valor (dict/list/JSON em texto) e troca cada token Fernet pelo texto original;
  2. confere que nenhum token restou;
  3. com --aplicar, regrava pela camada ORM, que cifra de novo com a chave do cliente (AES-256-GCM).
Sem --aplicar é uma simulação: tudo é feito em memória e desfeito (rollback).

Uso (na raiz do projeto; faça backup cifrado antes de --aplicar):
  .\\.venv\\Scripts\\python.exe scripts/repair_nested_legacy_fernet.py            # simulação
  .\\.venv\\Scripts\\python.exe scripts/repair_nested_legacy_fernet.py --aplicar
Nunca imprime conteúdo: só tabelas, colunas e contagens.
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from backend.app import db_models  # noqa: E402,F401  (registra os modelos)
from backend.app.database import Base, PlatformSessionLocal, platform_engine  # noqa: E402
from backend.app.field_crypto import ENCRYPTED  # noqa: E402
from reencrypt_fields import legacy_fernet, undo_legacy  # noqa: E402

TOKEN = re.compile(r"gAAAAA[\w-]{40,}={0,2}")


class Reparo:
    def __init__(self, fernet):
        self.fernet = fernet
        self.trocados = 0
        self.falhas = 0

    def _token(self, tok: str, onde: str) -> str:
        plain = undo_legacy(tok, self.fernet, onde)
        if plain == tok:  # não decifrou com a chave antiga: não mexe e registra
            self.falhas += 1
            return tok
        self.trocados += 1
        return plain

    def valor(self, v, onde: str):
        if isinstance(v, dict):
            return {k: self.valor(x, onde) for k, x in v.items()}
        if isinstance(v, list):
            return [self.valor(x, onde) for x in v]
        if not isinstance(v, str) or "gAAAAA" not in v:
            return v
        s = v.strip()
        if s.startswith("gAAAAA") and TOKEN.fullmatch(s):
            return self._token(s, onde)
        if s[:1] in "[{":
            try:
                return json.dumps(self.valor(json.loads(s), onde), ensure_ascii=False)
            except ValueError:
                pass
        return TOKEN.sub(lambda m: self._token(m.group(0), onde), v)


def restantes(v) -> int:
    texto = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return len(TOKEN.findall(texto or ""))


async def main(aplicar: bool) -> int:
    fernet = legacy_fernet()
    if fernet is None:
        sys.exit("Chave Fernet legada não encontrada (secrets/legacy_fernet.key).")
    modelos = {m.class_.__tablename__: m.class_ for m in Base.registry.mappers}
    rep = Reparo(fernet)
    sobrou = 0
    alteradas = 0
    async with PlatformSessionLocal() as db:
        for tabela, colunas in ENCRYPTED.items():
            cls = modelos.get(tabela)
            if cls is None:
                continue
            for obj in (await db.execute(select(cls))).scalars():
                mudou = False
                for col in colunas:
                    atual = getattr(obj, col, None)
                    if atual is None or "gAAAAA" not in (atual if isinstance(atual, str) else json.dumps(atual, default=str)):
                        continue
                    antes = rep.trocados
                    novo = rep.valor(atual, f"{tabela}.{col}")
                    if rep.trocados != antes:
                        setattr(obj, col, novo)
                        flag_modified(obj, col)
                        mudou = True
                        print(f"  {tabela}.{col}: {rep.trocados - antes} valor(es) recuperado(s)")
                    sobrou += restantes(novo)
                alteradas += mudou
        print(f"\nlinhas alteradas: {alteradas} | valores recuperados: {rep.trocados} | "
              f"tokens que não decifraram: {rep.falhas} | tokens restantes: {sobrou}")
        if rep.falhas or sobrou:
            await db.rollback()
            print("Nada gravado: há tokens que não puderam ser recuperados.")
            return 1
        if aplicar:
            await db.commit()
            print("Gravado (recifrado pela camada ORM).")
        else:
            await db.rollback()
            print("Simulação: nada foi gravado. Use --aplicar para gravar.")
    await platform_engine.dispose()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args().aplicar)))
