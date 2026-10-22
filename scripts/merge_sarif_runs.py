#!/usr/bin/env python3
"""Mescla múltiplas SARIF runs em uma só antes do upload.

O GitHub Code Scanning recusa um results.sarif com mais de uma run sob a
mesma categoria (desde 2025-07-21). O Codacy CLI às vezes gera mais de uma
run no mesmo arquivo — esse script combina rules e results de todas as
runs em uma única, sem depender de adivinhar por que o Codacy as separa
(mesma causa raiz e correção já confirmadas no SDK Node).
"""

import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python merge_sarif_runs.py <arquivo.sarif>", file=sys.stderr)
        return 1

    path = sys.argv[1]

    with open(path, encoding="utf-8") as handle:
        sarif = json.load(handle)

    runs = sarif.get("runs") or []
    if len(runs) <= 1:
        print(f"[merge_sarif_runs] {path} já tem {len(runs)} run(s), nada a fazer.")
        return 0

    first, *rest = runs

    rules_by_id = {rule["id"]: rule for rule in (first.get("tool", {}).get("driver", {}).get("rules") or [])}
    results = list(first.get("results") or [])

    for run in rest:
        for rule in run.get("tool", {}).get("driver", {}).get("rules") or []:
            rules_by_id.setdefault(rule["id"], rule)
        results.extend(run.get("results") or [])

    first.setdefault("tool", {}).setdefault("driver", {})["rules"] = list(rules_by_id.values())
    first["results"] = results

    sarif["runs"] = [first]

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(sarif, handle)

    print(f"[merge_sarif_runs] Mescladas {1 + len(rest)} runs em 1 ({len(results)} resultados) em {path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
