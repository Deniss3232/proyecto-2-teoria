# -*- coding: utf-8 -*-
"""
Interfaz interactiva:
- Pide ruta de gramática (p.ej., 1.txt o 1-cnf.txt)
- Detecta tokenizador:
    * Si los terminales son {'+', '*', '(', ')', 'id'} → expr_tokenize
    * Si hay palabras (she, eats, the, ...) → word_tokenize
- Permite forzar modo con --mode expr|words
- Comando 'cnf' imprime la gramática convertida/activa
"""

import argparse
from cyk_engine import (
    CFG, CNFConverter, expr_tokenize, word_tokenize,
    cyk_parse, reconstruct_tree
)

def detectar_modo(cnf: CFG) -> str:
    # terminales = símbolos que no son NT (no están como LHS)
    NT = set(cnf.rules.keys())
    terms = set()
    for rhss in cnf.rules.values():
        for rhs in rhss:
            for s in rhs:
                if s not in NT:
                    terms.add(s)
    expr_terms = {"+", "*", "(", ")", "id"}
    # si TODOS los terminales están en el conjunto de expresiones, asumimos expr
    if terms and terms.issubset(expr_terms):
        return "expr"
    return "words"

def pedir_ruta():
    ruta = input("Ruta de gramática (ej. 1.txt o 1-cnf.txt). Enter para '1.txt': ").strip()
    return ruta or "1.txt"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["expr", "words"], help="Forzar modo de tokenización.")
    args = ap.parse_args()

    print("=== CYK – Modo interactivo ===")
    print("Este programa lee tu gramática desde archivo y luego evalúa entradas.")
    print("Consejo: si tu gramática es la original con 'e' como epsilon, usa 1.txt; si ya está en CNF, usa 1-cnf.txt.\n")

    ruta = pedir_ruta()
    cfg_raw = CFG.load_from_file(ruta)

    # Si el archivo YA es CNF por nombre, no reconvertir
    if "cnf" in ruta.lower():
        cnf = cfg_raw
    else:
        cnf = CNFConverter(cfg_raw).to_cnf()

    # Detectar tokenizador (o forzar por flag)
    modo = args.mode or detectar_modo(cnf)
    tok = expr_tokenize if modo == "expr" else word_tokenize

    print(f"✔ Gramática cargada: símbolo inicial = {cnf.start}")
    print(f"✔ Modo de tokenización: {modo}\n")
    print("Escribe 'cnf' para ver la gramática activa; escribe 'q' para salir.\n")

    if modo == "expr":
        print("Ejemplos: id + id * id   |   ( id + id ) * id   |   (x+3)*y")
        print("Nota: cualquier identificador o número se interpreta como 'id'.\n")
    else:
        print("Ejemplos: She eats a cake  |  He drinks the juice  |  She eats a cake with a fork\n")

    while True:
        try:
            s = input("> ").strip()
        except EOFError:
            break
        if not s:
            continue
        if s.lower() in {"q", "quit", "exit"}:
            break
        if s.lower() == "cnf":
            print("\n CNF ")
            for A in sorted(cnf.rules.keys()):
                rhss = sorted(cnf.rules[A])
                rhs_strs = [" ".join(rhs) for rhs in rhss]
                print(f"{A} -> " + " | ".join(rhs_strs))
            print("-----------\n")
            continue

        tokens = tok(s)
        res = cyk_parse(cnf, tokens)
        print(f"Tokens: {tokens}")
        print("¿Pertenece al lenguaje? ->", "SÍ" if res.accepts else "NO")
        print(f"Tiempo CYK: {res.runtime_s*1000:.3f} ms")

        if res.accepts:
            tree = reconstruct_tree(tokens, res, cnf.start)
            if tree:
                print("\nÁrbol sintáctico (bracketed):")
                print(tree.bracketed(), "\n")

if __name__ == "__main__":
    main()
