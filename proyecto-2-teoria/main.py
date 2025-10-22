# -*- coding: utf-8 -*-

import re
from cyk_engine import (
    CFG, CNFConverter,
    expr_tokenize, word_tokenize,
    cyk_parse, reconstruct_tree
)

# ===================== Helpers de verbosidad =====================

def print_words_info(tokens):
    print("\n⟫ Análisis de entrada")
    print("   • Palabras:", tokens)
    print("   • Longitud:", len(tokens))

def print_cyk_table(tokens, res):
    """Imprime la tabla CYK por niveles (1..n) con un formato diferente."""
    n = len(tokens)
    if n == 0:
        print("\n⟫ Tabla CYK: (cadena vacía)")
        return

    print("\n⟫ Tabla CYK (niveles por longitud)")
    print("   " + "─" * 56)
    for L in range(1, n + 1):
        fila = []
        for i in range(0, n - L + 1):
            j = i + L - 1
            nts = sorted(res.table[i][j])
            celda = "{" + ", ".join(nts) + "}" if nts else "∅"
            fila.append(celda)
        print(f"   L={L:>2} │ " + " || ".join(fila))
    print("   " + "─" * 56)
    print("   idx │ " + "  ".join(f"[{k}]" for k in range(n)))
    base = "  ".join(
        "{" + ", ".join(sorted(res.table[i][i])) + "}" if res.table[i][i] else "∅"
        for i in range(n)
    )
    print("   L=1 │ " + base)
    print("   tok │ " + " | ".join(tokens))

def imprimir_cnf(cnf: CFG):
    print("\n⟫ Gramática activa (CNF)")
    print("   " + "-" * 56)
    for A in sorted(cnf.rules.keys()):
        rhss = sorted(cnf.rules[A])
        rhs_strs = [" ".join(rhs) for rhs in rhss]
        print(f"   {A} -> " + " | ".join(rhs_strs))
    print("   " + "-" * 56 + "\n")

def normalizar_w_prefijo(s: str) -> str:
    """
    Acepta entradas tipo:
      w = She eats a cake
      w: the cat drinks the beer;
      "she eats a cake"
    y devuelve solo la oración/expresión.
    """
    m = re.match(r'^\s*w\s*[:=]\s*(.*?);?\s*$', s, flags=re.IGNORECASE)
    s_norm = m.group(1) if m else s.strip()
    if len(s_norm) >= 2 and s_norm[0] == s_norm[-1] and s_norm[0] in {"'", '"'}:
        s_norm = s_norm[1:-1]
    return s_norm

# ===================== Núcleo de ejecución =====================

def ejecutar_cyk(ruta: str, modo: str):
    # 1) Cargar gramática
    cfg_raw = CFG.load_from_file(ruta)
    print(f"\n✔ Gramática cargada (símbolo inicial = {cfg_raw.start})")

    # 2) Convertir a CNF solo si el archivo no es CNF por nombre
    if "cnf" in ruta.lower():
        cnf = cfg_raw
        print("✔ Usando gramática ya en CNF.")
    else:
        cnf = CNFConverter(cfg_raw).to_cnf()
        print("✔ Conversión a CNF completada.")
    print()

    # 3) Elegir tokenizador
    tok = expr_tokenize if modo == "expr" else word_tokenize

    print("Escribe una entrada para evaluar; 'cnf' muestra la gramática; 'q' regresa al menú.")
    if modo == "expr":
        print("Ejemplos: id + id * id   |   ( id + id ) * id   |   (x+3)*y\n")
    else:
        print("Ejemplos: she eats a cake   |   he drinks the juice   |   she eats a cake with a fork\n")

    # 4) Loop interactivo
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
            imprimir_cnf(cnf)
            continue

        s_norm = normalizar_w_prefijo(s)
        tokens = tok(s_norm)
        res = cyk_parse(cnf, tokens)

        print(f"\n⟫ Tokens: {tokens}")
        print(f"⟫ Pertenece: {'SÍ' if res.accepts else 'NO'}   (t = {res.runtime_s*1000:.3f} ms)")

        # Info detallada y tabla
        print_words_info(tokens)
        print_cyk_table(tokens, res)

        # Árbol solo en formato bracketed
        if res.accepts:
            tree = reconstruct_tree(tokens, res, cnf.start)
            if tree:
                print("\n⟫ Árbol sintáctico (bracketed):")
                print("   " + tree.bracketed())

        # Mini resumen final
        print("⟫ Resumen:",
              "ACEPTADA " if res.accepts else "RECHAZADA ",
              f"— {len(tokens)} tokens — {res.runtime_s*1000:.2f} ms\n")

# ===================== Menú =====================

def menu_principal():
    while True:
        print("\n================ CYK – MENÚ ================")
        print("1) Gramática aritmética (1.txt o 1-cnf.txt)")
        print("2) Gramática en inglés (grammar-en.txt)")
        print("3) Salir")
        print("============================================")
        opcion = input("Elige una opción: ").strip()

        if opcion == "1":
            ruta = input("Ruta del archivo [Enter → 1.txt]: ").strip() or "1.txt"
            ejecutar_cyk(ruta, modo="expr")

        elif opcion == "2":
            ruta = input("Ruta del archivo [Enter → grammar-en.txt]: ").strip() or "grammar-en.txt"
            ejecutar_cyk(ruta, modo="words")

        elif opcion == "3":
            print("Listo. ")
            break
        else:
            print("Opción inválida. Intenta nuevamente.")

# ============ Main ===========

if __name__ == "__main__":
    print("=== PROYECTO CYK – Interfaz  ===")
    menu_principal()
