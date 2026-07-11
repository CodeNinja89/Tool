# Architecture Guide

How TOOL translates specification programs into Z3 SMT constraints and verifies properties.

## Pipeline Overview

```
.tool source
    │
    ▼
┌─────────────┐
│  Lark Parser │   (core/toolGrammar.lark + core/toolParser.py)
│              │   → produces a concrete syntax tree via Z3Transformer
└──────┬──────┘
       ▼
┌─────────────┐
│     AST      │   (core/toolAst.py)
│              │   → dataclass-based nodes: Program, Expr, Stmt, etc.
└──────┬──────┘
       ▼
┌──────────────────┐
│ Type Environment  │   (core/toolTypes.py)
│                  │   → builds symbol table from declarations section
└──────┬───────────┘
       ▼
┌──────────────────┐
│   Type Checker    │   (core/toolTypeChecker.py)
│                  │   → validates expression types, struct field access, etc.
└──────┬───────────┘
       ▼
┌──────────────────┐
│  SSA Transformer  │   (core/toolSSA.py)
│                  │   → x → x_0, x_1, x_2 ... (one version per assignment)
└──────┬───────────┘
       ▼
┌──────────────────┐
│  Z3 Translator    │   (core/toolZ3.py)
│                  │   → AST nodes → Z3 ExprRef / Solver constraints
└──────┬───────────┘
       ▼
┌──────────────────┐
│   Z3 Solver       │   (z3-solver library)
│                  │   → SAT / UNSAT / UNKNOWN + counter-example models
└──────────────────┘
```

Entry point: `test.py` orchestrates the full pipeline.

---

## Stage 1 — Parsing (`core/toolParser.py`)

The Lark parser reads `core/toolGrammar.lark` (a LALR grammar) and produces a parse tree. The `Z3Transformer` class walks the parse tree bottom-up, converting terminal symbols into AST dataclasses from `toolAst.py`.

Key transformer methods:
- `structured_program(items)` → `Program(declarations, preconditions, postconditions, specProgram)`
- `function_def(items)` → `FunctionDef(name, args, retName, retType, clauses)`
- Formula rules (`eq`, `lt`, `logic_and_op`, etc.) → `BinaryExpr(left, op, right)`
- `lvalue(items)` → chains of `VarRef` → `FieldAccess` / `SeqAccess`

The grammar supports C++-style comments and whitespace skipping.

---

## Stage 2 — Type Environment (`core/toolTypes.py`)

`TypeEnvironment.build(declarations)` iterates over the declarations section and populates:

| Attribute | Contents |
|-----------|----------|
| `variables` | `{name → type_string}` for all vars, consts, ghosts |
| `structs` | `{struct_name → {field_name → field_type}}` |
| `oracles` | `{oracle_name → FunctionDef AST node}` |
| `envs` | `{env_name → EnvDef AST node}` |
| `traces` | `{trace_name → TraceDef AST node}` |
| `linear_structs` | Set of struct names marked `linear` |
| `invisible_vars` | Set of ghost variable names |
| `constant_vars` | Set of const variable names |

---

## Stage 3 — Type Checking (`core/toolTypeChecker.py`)

The type checker validates:

1. **Preconditions** must be boolean expressions.
2. **Postconditions** must be boolean expressions.
3. **Assignments**: LHS and RHS types must match (or be compatible).
4. **Field access**: The object's type must have the accessed field.
5. **Sequence indexing**: Indexed type must be `seq[T]`.
6. **Oracle calls**: Argument count and types must match the oracle signature.
7. **Comparison operators**: Both operands must be the same type (or both numeric).

Type checking raises exceptions on errors rather than producing diagnostics — it is a hard gate before SSA transformation.

---

## Stage 4 — SSA Transformation (`core/toolSSA.py`)

The SSA (Static Single Assignment) transformer eliminates mutable variables by versioning them: every assignment to `x` produces a new name `x_N`.

### Versioning Scheme

- `_get_current_name("x")` → `"x_0"`, `"x_1"`, etc. (reads the latest version for RHS expressions)
- `_get_next_name("x")` → increments and returns `"x_N"` (LHS of assignments)

### Expression Transformation

`transform_expr(node)` recursively walks the AST:
- `VarRef("x")` → `VarRef("x_0")` (current version)
- `BinaryExpr(left, op, right)` → transforms both children
- `Quantifier(bound_var, ...)` → bound variables are **not** versioned (added to `bound_vars` set)
- `FuncCall(name, args)` → transforms argument expressions

### Statement Transformation

For assignments:
```
x := expr        →   x_N := transform_expr(expr)    where N = next_version(x)
node.val := expr →   node_N.val := ...              (struct field update becomes StructUpdate expr)
arr[i] := expr   →   arr_N[i] := ...                (SeqUpdate expr)
```

### Loop Handling

Loops are the most complex case. Since the number of iterations is unknown, the SSA transformer creates a **symbolic loop transition** (`LoopTransition` AST node):

1. **Pre-loop scope**: variable versions before the loop starts.
2. **Read scope**: symbolic versions at the start of an arbitrary i-th iteration.
3. **Write scope**: versions after executing the body once from the read scope.

The invariant is evaluated in all three scopes:
- `inv_pre` — base case (invariant holds before first iteration)
- `inv_read` — inductive hypothesis (invariant holds at start of iteration)
- `inv_write` — inductive proof (invariant holds after body execution)

### Branch Handling (If/Else)

For conditional branches, the transformer computes a **write set** (variables modified in either branch). Variables in the write set get a new version after the if statement; variables not modified keep their current version.

---

## Stage 5 — Z3 Translation (`core/toolZ3.py`)

The `Z3Translator` converts SSA-form AST nodes into Z3 SMT expressions.

### Sort Mapping

| TOOL type | Z3 sort |
|-----------|---------|
| `int` | `IntSort` (unbounded mathematical integer) |
| `bool` | `BoolSort` |
| `seq[T]` | `ArraySort(IntSort, inner_sort)` — infinite array indexed by int |
| `timestep` | `IntSort` |
| user struct `S` | `Datatype` with two constructors: `mk_S(...fields...)` and `null_S()` |

### Structs as Algebraic Datatypes

Every struct is compiled to a Z3 **datatype** with exactly two constructors:

1. `mk_StructName(field1, field2, ...)` — the "populated" constructor
2. `null_StructName()` — the null/empty constructor

This gives three automatic axioms from Z3:
- **Mutual exclusion**: `mk_S(...) != null_S()` is always true.
- **Recognizers**: `is_mk_S(t)` and `is_null_S(t)` are generated automatically.
- **Safe access**: Field accessors (`.field1`) only work on `mk_S` values.

### Oracle Translation

Oracles become Z3 **uninterpreted functions** (`z3.Function`). Their `assumes` clauses generate call-site checks, and their `returns` clauses become solver axioms.

The `OracleManager` class handles:
- Creating uninterpreted function declarations
- Registering returns-clause axioms
- Generating call-site precondition checks (as `CallSiteCheck` wrapper nodes)

### Quantifier Instantiation

Z3 needs **triggers** to instantiate quantifiers efficiently. The translator has a `_find_patterns()` method that searches for function applications involving bound variables to suggest as triggers.

---

## Stage 6 — Verification (`test.py`)

The main driver in `test.py` orchestrates the proof:

### Step 1 — Preconditions

Each precondition is SSA-transformed, Z3-translated, and added to the solver. A consistency check ensures preconditions are not contradictory (solver must return SAT or UNKNOWN).

### Step 2 — Program Transitions

The program body is processed statement by statement. Each produces a `transition_item`:

| Item Type | Handling |
|-----------|----------|
| Normal AST node (assignment, frame axiom) | Translate → add to solver |
| `CallSiteCheck` | Prove the oracle's assumes hold at this call site (negate + check UNSAT), then add as fact |
| `FactStmt` | Add directly to solver; check consistency |
| `AssertStmt` | Prove by negation (must be UNSAT); if proven, add to timeline |
| `LoopTransition` | Run loop induction: prove base case + inductive step via `verify_loop_transition()` |

### Step 3 — Postconditions

All postconditions are SSA-transformed and Z3-translated. They are conjoined with AND, then the conjunction is **negated** (De Morgan) and added to the solver. This hunts for counter-examples: if no counter-example exists (UNSAT), the property holds.

### Step 4 — Final Verdict

| Solver result | Meaning |
|---------------|---------|
| `unsat` | **PROVED** — negated postconditions are impossible; property holds for all executions |
| `sat` | **INVALID** — counter-example model printed showing a violating state |
| `unknown` | **UNKNOWN** — solver timed out or could not decide; reason printed |

---

## Key Design Decisions

### Why SSA?

SSA form eliminates the need for symbolic store reasoning. Instead of tracking "what is x at program point P?", each variable version (`x_0`, `x_1`, ...) is a distinct Z3 constant. This makes the translation to SMT straightforward and avoids complex lambda-lifting or separation logic.

### Why Oracles Instead of Implementations?

Oracles are **axiomatic** — they define what a function does mathematically, not how. This means:
- No need to verify the oracle's implementation (it has none).
- The verifier reasons about the contract directly.
- Complex operations (sorting, searching) can be specified concisely via quantified postconditions.

### Why Z3 Datatypes for Structs?

Z3 datatypes provide built-in null safety and structural reasoning without manual encoding. The two-constructor pattern (`mk_S` / `null_S`) mirrors how reference types work in practice: every struct value is either populated or null, and the solver enforces this distinction automatically.

---

## Known Limitations

1. **Bitwise operators** (`&`, `|`, `^`, `~`, `<<`, `>>`) are parsed but not all are implemented in the Z3 translator. The `&` operator raises `NotImplementedError`.
2. **No recursion** in program methods — oracles are axiomatic (no body), and the program section is purely imperative.
3. **Loop verification requires explicit invariants** — the tool does not synthesize them.
4. **Quantifier performance** depends on trigger selection; complex nested quantifiers may time out.
5. **Type system** supports `int`, `bool`, `seq[T]`, and user structs, but not generics or higher-order types.
