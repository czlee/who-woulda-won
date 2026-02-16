# Tiebreak test brainstorming notes

Notes from attempting to construct test data for Schulze tiebreak scenarios.
The user will write the actual test data.

## test_tiebreak_by_winning_strength

**Goal:** Two competitors tie on wins but differ in winning beatpath strength sum.

### Attempt 1: 3 competitors, 5 judges

```
     J1  J2  J3  J4  J5
A     1   1   1   2   3
B     2   3   2   1   1
C     3   2   3   3   2
```

Pairwise: A>B: 3-2, A>C: 3-2, B>C: 3-2. No cycles, all direct.
Path strengths: p[A][B]=3, p[A][C]=3, p[B][C]=3, rest 0.
Wins: A=2, B=1, C=0. No ties -- tiebreak not needed. **Failed.**

### Attempt 2: 4 competitors, 4 judges

```
     J1  J2  J3  J4
A     1   1   1   1
B     2   2   3   4
C     3   4   2   3
D     4   3   4   2
```

Pairwise (4 judges):
A>B: 4-0, A>C: 4-0, A>D: 4-0
B>C: 2-2 (tie), B>D: 2-2 (tie), C>D: 2-2 (tie)
All B/C/D matchups are 2-2 ties -- path strengths are 0 -- all three get 0 wins among themselves.
3-way tie where everything is equal. **Failed.**

### Attempt 3: 4 competitors, 5 judges (the code that was in the test)

A always 1st. B vs C is tied (split). B crushes D, C barely beats D.

```python
scoresheet = make_scoresheet("WinStr Tiebreak", {
    "J1": {"A": 1, "B": 2, "C": 3, "D": 4},
    "J2": {"A": 1, "B": 2, "C": 3, "D": 4},
    "J3": {"A": 1, "B": 3, "C": 2, "D": 4},
    "J4": {"A": 1, "B": 4, "C": 2, "D": 3},
    "J5": {"A": 1, "B": 4, "C": 2, "D": 3},
})
```

Assertions expected B and C to have same win count but B to rank above C due to winning strength.
**Status: needs verification that it actually produces the intended tie.**

### Approach that should work: 8 judges

Use enough judges so that B>D is much stronger than C>D, while B vs C is an exact tie.
For example, 8 judges where B and C split 4-4 on their head-to-head, but B beats D 7-1 while C beats D 5-3.

## test_tiebreak_by_total_strength

**Goal:** Two competitors with same wins, same winning beatpath strength sum, but different total beatpath strength sums.

### Key difficulty

In a non-cyclic setting, if A>B and A>C, then path B->A = 0 and C->A = 0. Losing beatpaths are zero, so total_strength equals winning_strength. **You need cycles for nonzero losing paths.**

### Attempt: 3 competitors with asymmetric cycle

A>B by 6-3, B>C by 5-4, C>A by 6-3. (9 judges)
- Direct: p[A][B]=6, p[B][C]=5, p[C][A]=6.
- Floyd:
  - k=A: p[C][B]=max(0,min(6,6))=6
  - k=B: p[A][C]=max(0,min(6,5))=5
  - k=C: p[B][A]=max(0,min(5,6))=5
- Final: p[A][B]=6, p[A][C]=5, p[B][A]=5, p[B][C]=5, p[C][A]=6, p[C][B]=6
- A vs B: 6>5 -> A wins. A vs C: 5<6 -> C wins. B vs C: 5<6 -> C wins.
- Wins: A=1, B=0, C=2. No tie. **Failed.**

### Attempt: symmetric 3-way cycle

A>B by 5, B>C by 5, C>A by 5. Same strength cycle -> all off-diag = 5 -> all ties -> wins = 1 each.
But winning_strength = 0 for all (no one wins). total_strength = 10 for all. Still tied. **Failed.**

### Attempt: asymmetric 3-way cycle variation

A>B by 5-4, B>C by 7-2, C>A by 5-4. (9 judges)
- Direct: p[A][B]=5, p[B][C]=7, p[C][A]=5.
- Floyd:
  - k=A: p[C][B]=max(0,min(5,5))=5
  - k=B: p[A][C]=max(0,min(5,7))=5
  - k=C: p[B][A]=max(0,min(7,5))=5
- Final: p[A][B]=5, p[A][C]=5, p[B][A]=5, p[B][C]=7, p[C][A]=5, p[C][B]=5
- A vs B: 5=5 (tie). A vs C: 5=5 (tie). B vs C: 7>5 (B wins).
- Wins: A=1, B=2, C=0. No tie. **Failed.**

### Attempt: 4 competitors with cycle among B, C, and a 3rd

A>B by 5, B>C by 3, C>A by 4. Plus everyone beats D by 6.
- Floyd: p[A][B]=5, p[A][C]=3, p[B][A]=3, p[B][C]=3, p[C][A]=4, p[C][B]=4
- A vs B: 5>3 -> A wins. A vs C: 3<4 -> C wins. B vs C: 3<4 -> C wins.
- Wins: A=2, B=1, C=3, D=0. No tie. **Failed.**

### Analysis: why this is so hard

For equal wins with 3 competitors, you need the cycle to produce equal beatpath comparisons, which only happens if all pairwise beatpath strengths are equal -- making all metrics equal too.

With more competitors (4-5), you can potentially get two competitors to tie on wins and winning_strength while differing on total_strength, but the construction is extremely contrived.

### Conclusion

Constructing a scenario where winning strengths tie but totals differ is extremely difficult in the Schulze method. The winning_strength tiebreak test validates the tiebreak mechanism works; the total_strength code path is simple enough that if winning works, total should too.

## test_partial_tiebreak

**Goal:** Tiebreak resolves some but not all ties in a group.

### Attempt: 4 competitors, 5 judges

```python
scoresheet = make_scoresheet("Partial Tiebreak", {
    "J1": {"A": 1, "B": 2, "C": 3, "D": 4},
    "J2": {"A": 4, "B": 3, "C": 2, "D": 1},
    "J3": {"A": 2, "B": 1, "C": 4, "D": 3},
    "J4": {"A": 3, "B": 4, "C": 1, "D": 2},
    "J5": {"A": 3, "B": 4, "C": 1, "D": 2},
})
```

All pairwise are close to tied. Test only asserted basic validity (code runs, tiebreak_used is valid, all competitors present).
**Status: needs analysis of what this actually produces, and whether it demonstrates partial tiebreak.**
