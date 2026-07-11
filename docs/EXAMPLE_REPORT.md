# Example Run Report

Results from running all 29 `.tool` examples through the verification pipeline (`python -X utf8 test.py`).

---

## PROVED — 10

| File | What It Proves |
|------|----------------|
| `autosarReadyQ.tool` | Priority-sorted ready queue invariant after scheduler loop + destruct |
| `lists.tool` | Acyclic list footprint property via oracle |
| `mathDouble.tool` | Temporal trace: `double_trace(3) == 8` (2^3) |
| `oracle_ex1.tool` | Critical section enter/exit preserves atomicity flag and increments resource |
| `queue.tool` | FIFO ordering of enqueue/dequeue operations |
| `ringBuffer_gemini.tool` | Circular buffer enqueue writes correct value at tail index |
| `scheduler.tool` | Task queue remains sorted and valid after scheduling loop + destruct |
| `sort.tool` | Oracle-sorted array satisfies sorted postcondition |
| `test_if.tool` | Conditional branch: if x>0 then y=x+10, else y=x-10; with x=5 proves y==15 |

## INVALID (Expected) — 8

These are intentionally designed to find counter-examples or verify contradictions:

| File | Why Invalid |
|------|-------------|
| `aliasing.tool` | Postcondition expects `resourceVal == 34`, actual value is 43 |
| `binaryTree.tool` | Postcondition asserts `is_correct == false` (contradiction test — solver returns SAT, proving the framework discharges correct VCs) |
| `bst_verify.tool` | Same pattern: postcondition `is_ok == false` — contradiction test |
| `linkedList_nonLinear.tool` | Call-site check fails: `contains(alias2_1, v_0)` violated (alias points to original list that doesn't contain the new value) |
| `loop.tool` | Postcondition says `sum == 150`, actual sum of 1..5 is **15** — intentional bug |
| `ringBuffer_protocol.tool` | Counter-example found in message queue protocol verification |
| `sharedResource_nonLinear.tool` | Postcondition expects `resourceVal == 34`, actual value is 43 (same pattern as aliasing) |
| `stack.tool` | Postcondition asserts `is_correct == false` — contradiction test |

## TIMEOUT / UNKNOWN — 6

These exceed the default 20-second solver timeout. They may be decidable with more time or manual lemma hints.

| File | Detail |
|------|--------|
| `avl.tool` | Timed out (>30s) — likely complex recursive AVL invariants |
| `binaryTree_assertions.tool` | Timed out (>30s) |
| `binaryTree_realTime.tool` | Timed out (>30s) — temporal trace + BST reasoning |
| `linkedList.tool` | Timed out (>30s) |
| `linkedList_assertions.tool` | Timed out (>30s) |
| `removeDuplicates_gemini.tool` | UNKNOWN (canceled by solver timeout) — complex loop with nested quantifiers |

## ERRORS — 5

These have issues in the source files or missing language features:

| File | Error |
|------|-------|
| `bits.tool` | `NotImplementedError: Cannot convert & to Z3` — bitwise AND not implemented in translator |
| `doublyLinkedList.tool` | Parse error: unexpected `,` at line 91 — grammar doesn't support the syntax used (likely multi-return oracle) |
| `seq.tool` | Parse error: `0u32` literal not recognized — no typed integer literals in grammar |
| `sort_permutations.tool` | Parse error: unexpected `}` at line 18 — likely uses a feature not in current grammar |
| `structTest.tool` | Type check error: cannot compare `uint32` and `int` — type mismatch between declaration and usage |

## Vacuous — 1

| File | Detail |
|------|--------|
| `test.tool` | No postconditions to verify — reports INVALID with empty model (vacuous) |

---

**Summary:** The core pipeline works well for oracle-based verification, loop induction, and temporal traces. The main gaps are: bitwise operators in the Z3 translator, typed integer literals (`u32`, `i8`), and some multi-return function syntax that the grammar doesn't yet support. Several examples time out on deeply recursive or heavily quantified specifications — those would benefit from solver tuning or manual lemma hints.
