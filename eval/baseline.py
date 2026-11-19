import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from collections import defaultdict

from ocr import extrair_texto
from regex_parser import (extrair_evidencias, normalizar_digitos,
                          normalizar_codigo, PADRAO_RG, extrair_emails_reparados)
from presidio_detector import analisar_texto

NORM = {
    "CPF": normalizar_digitos, "CARTAO": normalizar_digitos,
    "CNPJ": normalizar_codigo, "RG": normalizar_codigo,
    "EMAIL": lambda v: v.strip().casefold(),
}
CHAVE_REGEX = {"CPF": "cpfs_validos", "CNPJ": "cnpjs_validos",
               "CARTAO": "cartoes_credito_validados",
               "EMAIL": "emails", "RG": "rgs_rotulados"}
ENT_PRESIDIO = {"BR_CPF": "CPF", "BR_CNPJ": "CNPJ", "BR_CARTAO": "CARTAO",
                "EMAIL_ADDRESS": "EMAIL", "BR_RG": "RG"}

c = defaultdict(lambda: defaultdict(int))

for img in sorted(Path("eval/corpus").glob("*_*.[pj][np]g")):
    variante = "limpo" if "limpo" in img.name else "ruidoso"
    verdade = json.loads(img.with_suffix(".json").read_text(encoding="utf-8"))
    reais = {(v["tipo"], NORM[v["tipo"]](v["valor"])) for v in verdade}

    cache = img.with_suffix(".ocr.txt")
    if cache.exists():
        texto = cache.read_text(encoding="utf-8")
    else:
        text = extrair_texto(texto)
        cache.write_text(text, encoding="utf-8")
    ev = extrair_evidencias(texto)
    regex = {(t, NORM[t](v)) for t, k in CHAVE_REGEX.items() for v in ev[k]}
    regex |= {("EMAIL", NORM["EMAIL"](e["valor"])) for e in extrair_emails_reparados(texto)}

    pres = set()
    for r in analisar_texto(texto):
        t = ENT_PRESIDIO.get(r.entity_type)
        if not t:
            continue
        trecho = texto[r.start:r.end]
        if t == "RG" and (m := PADRAO_RG.search(trecho)):
            trecho = m.group(1)
        pres.add((t, NORM[t](trecho)))

    for tipo, valor in reais:
        c[(variante, tipo)]["total"] += 1
        c[(variante, tipo)]["ocr_ok"] += valor in NORM[tipo](texto)
    for nome, previstos in (("regex", regex), ("presidio", pres)):
        for tipo in NORM:
            p = {x for x in previstos if x[0] == tipo}
            r = {x for x in reais if x[0] == tipo}
            c[(variante, tipo)][f"{nome}_tp"] += len(p & r)
            c[(variante, tipo)][f"{nome}_fp"] += len(p - r)

print(f"{'variante':8} {'tipo':7} {'OCR leu':>8} {'regex rec':>10} "
      f"{'regex FP':>9} {'pres rec':>9} {'pres FP':>8}")
for (var, tipo), m in sorted(c.items()):
    t = m["total"] or 1
    print(f"{var:8} {tipo:7} {m['ocr_ok']/t:8.0%} {m['regex_tp']/t:10.0%} "
          f"{m['regex_fp']:9d} {m['presidio_tp']/t:9.0%} {m['presidio_fp']:8d}")