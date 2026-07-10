# TOOL — Typed Oracle Oriented Language

A formal verification tool that translates high-level specification programs into Z3 SMT constraints, then proves (or disproves) mathematical properties about program behavior.

## At a Glance

TOOL lets you write imperative-style programs with axiomatic function contracts (**oracles**), then automatically verifies preconditions and postconditions using the **Z3 theorem prover**. The pipeline is:

```
.tool source → Lark parser → AST → Type checker → SSA transformation → Z3 translation → SMT solver
```

## Quick Start

### Prerequisites

- Python 3.12+
- `lark` and `z3-solver` packages

```bash
pip install lark z3-solver
```

On Windows, run with UTF-8 mode to avoid console encoding issues:

```bash
python -X utf8 test.py <example>.tool
```

### Hello Verification

Create a file `hello.tool`:

```
%% declarations
x: int;
y: int;

%% preconditions
x == 5;

%% postconditions
y == 10;

%% program
y := x + x;
```

Run it:

```bash
python -X utf8 test.py hello.tool
```

Output: `VERDICT: PROVED` — the postcondition `y == 10` follows from the precondition and program.

## Language Tour

A TOOL program has four sections, each prefixed with `%%`:

### 1. Declarations (`%% declarations`)

Declare variables, structs, constants, invisible (ghost) variables, and oracles.

```
x: int;
n: int;
arr: seq[int];

const MAX_SIZE: int;
invisible ghost_count: int;

struct Node {
    val: int;
    next: Node;
}
```

### 2. Oracles — Axiomatic Function Contracts

Oracles are pure functions defined by their **assumes** (preconditions) and **returns** (postconditions), not by implementation. Z3 treats them as uninterpreted functions constrained by these axioms.

```
oracle sort(old_seq: seq[int], len: int) -> new_seq: seq[int] {
    assumes len >= 0;
    returns (forall i: int . forall j: int .
        !(i >= 0 && i < len && j > i && j < len) || (new_seq[i] <= new_seq[j])) &&
        // permutation property...
}
```

### 3. Preconditions (`%% preconditions`)

Assumptions about the initial state before the program runs:

```
arr_len >= 0;
head == 0;
tail == 0;
```

### 4. Program (`%% program`)

Imperative statements that transform state:

| Statement | Syntax | Description |
|-----------|--------|-------------|
| Assignment | `x := expr;` | Assign a value |
| Assert | `assert formula;` | Prove a property at this point (fails verification if false) |
| Fact | `fact formula;` | Add an axiom to the solver timeline |
| While | `while (cond) invariant inv { body }` | Loop with invariant for induction |
| If | `if (cond) { then } else { else }` | Conditional branching |

### 5. Postconditions (`%% postconditions`)

Properties that must hold after the program executes:

```
is_sorted == true;
head <= tail;
```

## Examples

The `example/` directory contains verification specifications for data structures and algorithms:

| File | What It Proves | Status |
|------|----------------|--------|
| `sort.tool` | Oracle-sorted array is sorted | PROVED |
| `queue.tool` | FIFO ordering of enqueue/dequeue | PROVED |
| `lists.tool` | Acyclic list footprint property | PROVED |
| `stack.tool` | Push-then-pop returns original value | (see notes) |
| `loop.tool` | Summation loop produces correct result | INVALID (intentional bug: postcondition says 150, actual sum is 15) |
| `bits.tool` | Bitwise flag checking | (requires `&` operator support) |

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a deep dive into the verification pipeline.

## Language Reference

See [docs/LANGUAGE_REFERENCE.md](docs/LANGUAGE_REFERENCE.md) for complete syntax documentation.
