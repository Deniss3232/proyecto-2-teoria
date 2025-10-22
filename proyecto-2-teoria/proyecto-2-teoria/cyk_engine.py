# -*- coding: utf-8 -*-
"""
Motor CYK con:
- Carga de gramática desde archivo (A -> α | β | ...), epsilon como 'e'
- Conversión a CNF (elimina ε, unitarias, terminales-en-reglas-largas, binariza)
- CYK + reconstrucción de árbol (bracketed)
- Dos tokenizadores:
  1) expr_tokenize: para expresiones (+, *, (, ), id, números/identificadores → 'id')
  2) word_tokenize: para oraciones en inglés (minúsculas, quita puntuación)
"""

from __future__ import annotations
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Iterable, Optional
import time, os, re

# ===================== Tokenizadores =====================

def expr_tokenize(s: str) -> List[str]:
    """Tokeniza expresiones aritméticas. Cualquier identificador o número -> 'id'."""
    out: List[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1; continue
        if c in "+*()":
            out.append(c); i += 1; continue
        if c.isalnum() or c == "_":
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] == "_"): j += 1
            out.append("id"); i = j; continue
        i += 1
    return out

_word_clean_re = re.compile(r"[^a-z'\s]")

def word_tokenize(s: str) -> List[str]:
    """Tokeniza oraciones en inglés: minúsculas, quita puntuación, separa por espacios."""
    s = s.lower()
    s = _word_clean_re.sub(" ", s)
    return [t for t in s.split() if t]

# ===================== Utilidades loader =====================

def strip_comments(line: str) -> str:
    pos = line.find('#')
    return line if pos < 0 else line[:pos]

class CFG:
    def __init__(self, start_symbol: str, rules: Dict[str, Set[Tuple[str, ...]]], start_nullable: bool = False):
        self.start = start_symbol
        self.rules = {A: set(Bs) for A, Bs in rules.items()}
        self.start_nullable = start_nullable

    @staticmethod
    def load_from_file(path: str) -> "CFG":
        """Lee archivo 'A -> α | β | ...' (epsilon como 'e'). Start = primer LHS."""
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        rules: Dict[str, Set[Tuple[str, ...]]] = defaultdict(set)
        order: List[str] = []

        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = strip_comments(raw).strip()
                if not line: continue
                if "->" not in line: raise ValueError(f"Regla inválida: {line}")
                lhs, rhs_all = [x.strip() for x in line.split("->", 1)]
                if not lhs: raise ValueError(f"LHS vacío: {line}")
                if lhs not in rules: order.append(lhs)
                alts = [a.strip() for a in rhs_all.split("|")]
                for alt in alts:
                    if alt == "" or alt.lower() == "e":
                        rules[lhs].add(("ε",))
                    else:
                        rules[lhs].add(tuple(alt.split()))

        if not order: raise ValueError("Gramática vacía.")
        return CFG(order[0], rules)

# ===================== Conversión a CNF =====================

class CNFConverter:
    def __init__(self, cfg: CFG):
        self.cfg = cfg
        self._fresh_id = 0

    def _fresh(self, p: str) -> str:
        self._fresh_id += 1
        return f"{p}_{self._fresh_id}"

    def _nonterms(self, rules): return set(rules.keys())

    def remove_unreachable(self, start, rules):
        reach = {start}; changed = True
        while changed:
            changed = False
            for A in list(reach):
                for rhs in rules.get(A, set()):
                    for X in rhs:
                        if X in rules and X not in reach:
                            reach.add(X); changed = True
        return {A: set(Bs) for A, Bs in rules.items() if A in reach}

    def remove_epsilon(self, start, rules):
        nullable = {A for A, rhss in rules.items() if ("ε",) in rhss}
        changed = True
        while changed:
            changed = False
            for A, rhss in rules.items():
                if A in nullable: continue
                for rhs in rhss:
                    if rhs == ("ε",): continue
                    if all(sym in rules and sym in nullable for sym in rhs):
                        nullable.add(A); changed = True; break
        start_nullable = start in nullable

        new = {A: set() for A in rules}
        from itertools import chain, combinations
        for A, rhss in rules.items():
            for rhs in rhss:
                if rhs == ("ε",): continue
                pos = [i for i, s in enumerate(rhs) if s in rules and s in nullable]
                def subs(it): 
                    s = list(it); 
                    return chain.from_iterable(combinations(s, r) for r in range(len(s)+1))
                any_added = False
                for sub in subs(pos):
                    nrhs = tuple(sym for i, sym in enumerate(rhs) if i not in sub)
                    if len(nrhs) == 0:
                        if A == start and start_nullable:
                            pass
                        continue
                    new[A].add(nrhs); any_added = True
                if not pos: new[A].add(rhs)
        new = {A: set(rhss) for A, rhss in new.items() if rhss}
        return new, start_nullable

    def remove_unit(self, rules):
        NT = self._nonterms(rules)
        unit_next: Dict[str, Set[str]] = defaultdict(set)
        for A, rhss in rules.items():
            for rhs in rhss:
                if len(rhs) == 1 and rhs[0] in NT:
                    unit_next[A].add(rhs[0])

        closure = {A: {A} for A in NT}
        for A in NT:
            q = deque(unit_next[A])
            while q:
                B = q.popleft()
                if B in closure[A]: continue
                closure[A].add(B)
                for C in unit_next.get(B, set()): q.append(C)

        new = {A: set() for A in NT}
        for A in NT:
            for B in closure[A]:
                for rhs in rules.get(B, set()):
                    if not (len(rhs) == 1 and rhs[0] in NT):
                        new[A].add(rhs)
        return new

    def terminals_to_unaries(self, rules):
        NT = self._nonterms(rules)
        term2nt: Dict[str, str] = {}
        new = {A: set() for A in NT}
        def nt_for(t: str):
            if t not in term2nt: term2nt[t] = self._fresh(f"T_{t}")
            return term2nt[t]
        for A, rhss in rules.items():
            for rhs in rhss:
                if len(rhs) >= 2:
                    rep = []
                    for s in rhs:
                        rep.append(s if s in NT else nt_for(s))
                    new[A].add(tuple(rep))
                else:
                    new[A].add(rhs)
        for t, nt in term2nt.items():
            new.setdefault(nt, set()).add((t,))
        return new, term2nt

    def binarize(self, rules):
        new: Dict[str, Set[Tuple[str, ...]]] = {A: set() for A in rules}
        for A, rhss in rules.items():
            for rhs in rhss:
                if len(rhs) <= 2:
                    new[A].add(rhs)
                else:
                    xs = list(rhs)
                    left, rest = xs[0], xs[1:]
                    prev = self._fresh("BIN")
                    new[A].add((left, prev))
                    while len(rest) > 2:
                        nxt_left = rest[0]
                        nxt = self._fresh("BIN")
                        new.setdefault(prev, set()).add((nxt_left, nxt))
                        prev = nxt
                        rest = rest[1:]
                    new.setdefault(prev, set()).add((rest[0], rest[1]))
        return new

    def to_cnf(self) -> CFG:
        rules = self.remove_unreachable(self.cfg.start, self.cfg.rules)
        rules, start_nullable = self.remove_epsilon(self.cfg.start, rules)
        rules = self.remove_unit(rules)
        rules, _ = self.terminals_to_unaries(rules)
        rules = self.binarize(rules)
        return CFG(self.cfg.start, rules, start_nullable)

# ===================== CYK + Árbol =====================

class CYKResult:
    def __init__(self, accepts: bool, runtime_s: float, table, back):
        self.accepts = accepts
        self.runtime_s = runtime_s
        self.table = table
        self.back = back

def cyk_parse(cnf: CFG, tokens: List[str]) -> CYKResult:
    n = len(tokens)
    if n == 0:
        return CYKResult(cnf.start_nullable, 0.0, [], {})
    rhs2lhs: Dict[Tuple[str, ...], Set[str]] = defaultdict(set)
    for A, rhss in cnf.rules.items():
        for rhs in rhss:
            rhs2lhs[rhs].add(A)

    table: List[List[Set[str]]] = [[set() for _ in range(n)] for _ in range(n)]
    back: Dict[Tuple[int, int, str], Tuple] = {}
    t0 = time.perf_counter()

    for i, w in enumerate(tokens):
        for A in rhs2lhs.get((w,), set()):
            table[i][i].add(A)
            back[(i, i, A)] = ("unary", w)

    for L in range(2, n + 1):
        for i in range(0, n - L + 1):
            j = i + L - 1
            for k in range(i, j):
                for B in table[i][k]:
                    for C in table[k + 1][j]:
                        for A in rhs2lhs.get((B, C), set()):
                            if A not in table[i][j]:
                                table[i][j].add(A)
                                back[(i, j, A)] = ("binary", k, B, C)

    return CYKResult(cnf.start in table[0][n - 1], time.perf_counter() - t0, table, back)

class ParseTreeNode:
    def __init__(self, label: str, children: Optional[List["ParseTreeNode"]] = None):
        self.label = label
        self.children = children or []
    def bracketed(self) -> str:
        if not self.children: return self.label
        return "(" + self.label + " " + " ".join(ch.bracketed() for ch in self.children) + ")"

def reconstruct_tree(tokens: List[str], res: CYKResult, start_symbol: str) -> Optional[ParseTreeNode]:
    n = len(tokens)
    if n == 0: return ParseTreeNode(start_symbol, [ParseTreeNode("ε")]) if res.accepts else None
    def build(i, j, A):
        info = res.back.get((i, j, A))
        if not info: return None
        if info[0] == "unary":
            return ParseTreeNode(A, [ParseTreeNode(info[1])])
        _, k, B, C = info
        L = build(i, k, B); R = build(k + 1, j, C)
        if not L or not R: return None
        return ParseTreeNode(A, [L, R])
    t = build(0, n - 1, start_symbol)
    return t
