# TOOL Language Reference

Complete syntax and semantics for the Typed Oracle Oriented Language.

## Program Structure

Every `.tool` file has exactly four sections, in this order:

```
%% declarations
...

%% preconditions
...

%% postconditions
...

%% program
...
```

Each section is introduced by `%% <name>`. Sections may be empty (no formulas/statements after the header). Comments are `//` line comments only — the grammar imports Lark's `CPP_COMMENT`, so `/* block */` comments are **not** supported.

---

## Declarations Section

### Variable Declaration

```
name: type;
```

Declares a mutable variable. The variable starts as an unconstrained symbolic value of the given type.

```
x: int;
arr: seq[int];
node: TreeNode;
```

### Constant Declaration

```
const name: type;
```

Declares a variable that cannot be reassigned in the program body.

```
const MAX_SIZE: int;
```

### Invisible (Ghost) Variable

```
invisible name: type;
```

Declares a variable used only for specification — it does not appear in the compiled output but is available to the verifier.

```
invisible step_count: int;
```

### Struct Definition

```
[linear] struct Name {
    field1: type;
    field2: type;
}
```

Defines a user-defined type with named fields. Fields can reference the struct itself (recursive types).

```
struct Node {
    val: int;
    next: Node;   // recursive field
}

linear struct Resource {
    data: int;
}
```

#### Linear structs

The optional `linear` keyword marks a struct as a **linear type**: any variable of that type is a resource that must be *consumed exactly once*. This is a compile-time discipline enforced entirely by the type checker (`core/toolTypeChecker.py`) — it adds no Z3 constraints and has no effect on the SMT translation.

The checker tracks every live linear variable in a set called *delta* and enforces:

- **Consume-on-use** — reading a linear variable (a plain reference) removes it from delta. Reading it again raises a **Use-After-Free** error.
- **`refer` borrows** — an oracle parameter marked `refer` (and the RHS of an assignment into an `invisible` variable) reads *without* consuming, so the resource stays live.
- **Reassignment replenishes** — assigning to a linear variable puts it back into delta, making it live again.
- **Balanced branches** — the two arms of an `if`/`else` must consume the same resources; otherwise a *Linear Type Error* is raised.
- **Loop neutrality** — a `while` body may not net-consume a linear resource (delta must be unchanged across one iteration).
- **No leaks** — at the end of the program delta must be empty. Any linear variable never consumed raises a **Memory Leak Error**.

The intent is to model single-ownership / move semantics (as in Rust or separation logic) so specifications can reason about resources like memory, handles, or locks that must not be duplicated or dropped.

```
linear struct Resource {
    data: int;
}
```

### Oracle Definition

Oracles are **axiomatic functions** — pure functions defined by their contract, not implementation. They are translated to Z3 uninterpreted functions constrained by their assumes/returns clauses.

```
oracle name(param1: type, param2: type) -> resultName: returnType {
    assumes precondition;
    returns postcondition;
}
```

- **`assumes`** — precondition that the caller must satisfy. Checked at every call site.
- **`returns`** — postcondition relating inputs to outputs. Added as an axiom to the solver.

Multiple `assumes` and `returns` clauses are allowed (all are conjoined).

```
oracle enqueue(mem: seq[int], t: int, elem: int) -> new_mem: seq[int] {
    assumes t >= 0;
    returns (new_mem[t] == elem) &&
            (forall i: int . (i != t) || (new_mem[i] == mem[i])) &&
            (new_mem.length == mem.length + 1);
}
```

### Env Definition

Declares an environment function signature without a body. Used for real-time and temporal reasoning.

```
env name(arg1: type, arg2: type) -> resultName: returnType;
```

### Trace Definition

Defines a temporal trace with init and step formulas over a timestep variable.

```
trace name(t: timestep) -> resultName: returnType {
    init: formula;
    step: formula;
}
```

---

## Types

| Type | Description |
|------|-------------|
| `int` | Unbounded mathematical integer (maps to Z3 IntSort) |
| `bool` | Boolean value (`true` / `false`) |
| `seq[T]` | Infinite sequence of type T, indexed by int (maps to Z3 ArraySort) |
| `timestep` | Alias for `int`, used in trace definitions |
| `Name` | User-defined struct type |

> **Sized integers (partial support).** Some examples (`seq.tool`, `test.tool`, `structTest.tool`) declare fixed-width types such as `uint32`. The grammar parses these as ordinary type names, and the Z3 translator has a branch for unsigned arithmetic (`left_type.startswith("uint")`). However, they are **not yet fully wired**: `get_z3_sort` has no `uint*`/sized-int case (it raises `NotImplementedError`), and the type checker's `NUMERIC_TYPES` set is `{"int", "timestamp"}`, which omits both the sized types and — apparently by typo — `timestep`. Treat sized integers as experimental until these are reconciled; use `int` for reliable verification.

---

## Expressions

### Literals

```
42          // integer
true        // boolean true
false       // boolean false
null        // null value for struct types
```

### Variables and Access

```
x                   // variable reference
node.val            // field access
node.next.val       // chained field access
arr[i]              // sequence index access
arr[i].val          // combined index + field access
```

### Arithmetic Operators

| Operator | Meaning | Precedence (high → low) |
|----------|---------|------------------------|
| `-x` | Unary negation | 1 |
| `*`, `/`, `%` | Multiply, divide, modulo | 2 |
| `+`, `-` | Add, subtract | 3 |

### Bitwise Operators

| Operator | Meaning | Precedence (high → low) |
|----------|---------|------------------------|
| `~x` | Bitwise NOT | 1 |
| `<<`, `>>` | Shift left/right | 2 |
| `&` | Bitwise AND | 3 |
| `^` | Bitwise XOR | 4 |
| `\|` | Bitwise OR | 5 |

> **Note:** Bitwise operators (`&`, `|`, `^`, `~`, `<<`, `>>`) are parsed by the grammar but may not be fully implemented in the Z3 translator. See architecture notes.

### Comparison Operators

```
==    !=    <    >    <=    >=
```

### Logical Operators

| Operator | Meaning | Precedence (high → low) |
|----------|---------|------------------------|
| `!x` | NOT | 1 |
| `&&` | AND | 2 |
| `\|\|` | OR | 3 |

### Ternary (ITE) Expression

```
condition ? true_expr : false_expr
```

### Quantifiers

```
forall x: type . body_expr    // universal quantification
exists x: type . body_expr    // existential quantification
```

The bound variable `x` is scoped to `body_expr`. The dot (`.`) separates the binding from the body.

```
forall i: int . (i >= 0 && i < len) || arr[i] >= 0
exists j: int . j >= 0 && arr[j] == target
```

### Function Calls

```
oracle_name(arg1, arg2, ...)
```

Calls an oracle. The arguments are evaluated, the oracle's assumes clauses are checked at the call site, and its returns clause is added as a solver axiom.

---

## Preconditions Section

A list of formulas (each terminated by `;`) that constrain the initial state:

```
%% preconditions
n >= 0;
arr.length > 0;
is_sorted(arr) == true;
```

All preconditions are conjoined and added to the Z3 solver before any program transitions.

---

## Postconditions Section

A list of formulas (each terminated by `;`) that must hold after the program executes:

```
%% postconditions
result >= 0;
is_sorted == true;
```

All postconditions are conjoined, then **negated** and added to the solver. If the solver returns UNSAT, the property is proven. If SAT, a counter-example model is printed.

---

## Program Section

### Assignment

```
lvalue := expression;
```

```
x := 0;
node.val := 42;
arr[i] := x + y;
```

### Assert Statement

```
assert formula;
```

Proves that `formula` holds at this point in the program. If the solver finds a counter-example, verification fails with a model. The assertion is added to the solver timeline after proof (so later statements can use it).

```
assert x >= 0;
```

### Fact Statement

```
fact formula;
```

Adds `formula` as an axiom to the solver timeline without proving it first. Use for introducing external knowledge or intermediate lemmas. If the fact contradicts the current state, verification fails with a contradiction error.

```
fact (x * x >= 0);
```

### While Loop

```
while (condition) invariant invariant_expr {
    body_statements
}
```

The loop is verified by **induction**:

1. **Base case:** The invariant holds before the first iteration (checked against preconditions + prior program state).
2. **Inductive step:** Assuming the invariant holds at the start of an arbitrary iteration and the loop condition is true, the invariant holds after executing the body.
3. **Post-loop:** When the loop exits (`!condition`), the invariant still holds.

The invariant is essential — without it, the tool cannot reason about unbounded iterations.

```
while (i > 0) invariant (sum == n*(n+1)/2 - i*(i+1)/2 && i >= 0) {
    sum := sum + i;
    i := i - 1;
}
```

### If Statement

```
if (condition) {
    then_statements
} else {
    else_statements   // optional
}
```

Both branches are explored symbolically. Variables modified in either branch get a new SSA version after the if statement.

---

## Grammar (Lark EBNF)

The full grammar is in `core/toolGrammar.lark`. Key rules:

```ebnf
start: structured_program
structured_program: declarations_section preconditions_section postconditions_section program_section

declarations_section: "%% declarations" declaration*
preconditions_section: "%% preconditions" (formula ";")*
postconditions_section: "%% postconditions" (formula ";")*
program_section: "%% program" statement*

?declaration: var_decl | const_decl | function_def | struct_def | invisible_decl | env_def | trace_def
var_decl: NAME ":" type ";"
const_decl: "const" NAME ":" type ";"
struct_def: [LINEAR] "struct" NAME "{" (NAME ":" type ";")+ "}"
invisible_decl: INVISIBLE NAME ":" type ";"

function_def: "oracle" NAME "(" [arg_list] ")" "->" NAME ":" type "{" function_body "}"
env_def: "env" NAME "(" [arg_list] ")" "->" NAME ":" type ";"
trace_def: "trace" NAME "(" NAME ":" "timestep" ")" "->" NAME ":" type "{" trace_body "}"

?statement: assign_stmt | while_stmt | if_stmt | assert_stmt | block_stmt | fact_stmt
assign_stmt: lvalue ":=" expr ";"
assert_stmt: "assert" formula ";"
fact_stmt: "fact" formula ";"
while_stmt: "while" "(" formula ")" ["invariant" formula] block_stmt
if_stmt: "if" "(" formula ")" block_stmt ["else" block_stmt]

?type: base_type | "seq" "[" type "]" | NAME
!base_type: "int" | "bool" | "timestep"
```
