# TOOL Static Type Checker & Linear Resource Engine (`toolTypeChecker.py`) Documentation

**Module:** `core/toolTypeChecker.py`

**Language:** Python 3

**Role:** Implements the `TypeChecker` class, which enforces static type safety, operator compatibility, immutability constraints, and substructural linear resource typing across TOOL Abstract Syntax Trees.

---

## 1. Architectural Overview & Design Objectives

The `TypeChecker` class performs static semantic analysis on parsed TOOL programs before they are transformed into Single Static Assignment (SSA) form or translated to Z3 SMT terms. It operates over the symbol table provided by `TypeEnvironment` ($\Gamma$) and maintains an internal resource tracking state ($\Delta$) to enforce two complementary typing regimes:

1. **Standard Algebraic & Logical Type Checking:** Ensures that operators, function arguments, return types, struct fields, and control-flow predicates are well-typed.


2. **Substructural Linear Resource Typing:** For user-defined structs marked with the `linear` keyword (`linear struct`), the type checker enforces a **linear ownership model**. Linear resources must be consumed exactly once across all execution paths, guaranteeing the absence of **Use-After-Free** bugs and **Memory Leaks** at the language level.



---

## 2. Type Compatibility & Numeric Interoperability

```python
NUMERIC_TYPES = {
    "int",
    "timestep"
}

```

TOOL supports unbounded mathematical integers (`"int"`) and discrete temporal step indices (`"timestep"`). The helper method `_types_compatible(actual, expected) -> bool` defines the equivalence rules between types:

* **Exact Match:** Returns `True` if `actual == expected`.


* **Numeric Interoperability:** Returns `True` if the set `{actual, expected}` is equal to `{"int", "timestep"}`. This allows literal integer constants and mathematical operations to interoperate seamlessly with temporal trace step variables without explicit casting.


* **Otherwise:** Returns `False`.



---

## 3. Linear Resource Engine ($\Delta$ Tracking)

The type checker tracks active linear resources using the dictionary `self.delta: Dict[str, str]`, which maps available linear variable names to their struct type signatures. A boolean flag, `self.enforce_linearity`, toggles whether linear resource rules are active during evaluation.

```
                [Global Linear Variables Initialized in Δ]
                                    │
                                    ▼
                      ┌───────────────────────────┐
                      │    Variable Reference     │
                      └─────────────┬─────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
        [is_refer == True]                   [is_refer == False]
    (e.g., refer arg / invisible var)         (Concrete Value Read)
                  │                                   │
                  ▼                                   ▼
         Δ Remains Unchanged              Is variable in Δ?
                                           ├── YES ──► Remove from Δ (Consumed)
                                           └── NO  ──► Raise Use-After-Free Error

```

### Linearity Enforcement Rules

1. **Resource Consumption (Read):** When a variable reference (`VarRef`) referencing a linear struct is evaluated with `is_refer=False` and `self.enforce_linearity=True`, it is permanently removed from `self.delta`. If the variable is not found in `self.delta`, the checker raises a **Use-After-Free Error**.


2. **Reference Borrowing (`is_refer=True`):** When linear structs are passed to oracle parameters marked with `refer`, or read during assignments to `invisible` variables, `is_refer` is set to `True`. This bypasses resource consumption, leaving `self.delta` intact.


3. **Resource Replenishment (Write):** Assigning a linear struct value to a variable via `AssignStmt` re-registers the variable in `self.delta` (unless the assignment targets an `invisible` variable).


4. **Branch Consistency (`if`/`else`):** Linear resources consumed in the `then_block` of an `IfStmt` must be identical to those consumed in the `else_block`. Mismatched resource states raise a **Linear Type Error**.


5. **Loop Invariance (`while`):** A `while` loop body must not permanently consume or leak linear resources across iterations (`delta_before == delta_after`).


6. **Scope Exit Anti-Leak Check:** When program verification completes, `self.delta` must be empty. Any unconsumed linear variables remaining in `self.delta` raise a **Memory Leak Error**.



---

## 4. Expression Type Resolution (`get_expr_type`)

```python
def get_expr_type(self, expr: ASTNode, is_refer: bool = False) -> str:

```

The `get_expr_type` method recursively computes and validates the type of any AST expression (`Expr`), enforcing operator contracts and linear ownership rules.

### Expression Evaluation Rules Table

| AST Expression Node | Resolution Logic & Type Checking Rules | Return Type |
| --- | --- | --- |
| `VarRef` | 1. Strips SSA version suffixes (e.g., `x_0` $\rightarrow$ `x` if the suffix after `_` is numeric).

<br>

<br>2. Looks up the base variable type in `env.get_var_type(base_name)`.

<br>

<br>3. If `enforce_linearity=True` and the type is linear: checks `self.delta`. If present and `not is_refer`, removes `base_name` from `delta`. If missing, raises `Exception("Use-After-Free Error: ...")`.

 | Declared variable type

 |
| `Literal` | Checks literal value string: `"true"`/`"false"` $\rightarrow$ `"bool"`; `"null"` $\rightarrow$ `"null"` (wildcard type); otherwise $\rightarrow$ `"int"`.

 | `"bool"`, `"null"`, or `"int"`<br> |
| `BinaryExpr` (`&&`, `||`) | Enforces that `left_type == "bool"` and `right_type == "bool"`.

 | `"bool"`<br> |
| `BinaryExpr` (`==`, `!=`) | 1. Allows `"null"` wildcard comparisons against any user-defined struct type.

<br>

<br>2. Otherwise, requires `_types_compatible(left_type, right_type)`.

 | `"bool"`<br> |
| `BinaryExpr` (`<`, `>`, `<=`, `>=`) | Requires both operands to belong to `NUMERIC_TYPES` (`"int"` or `"timestep"`).

 | `"bool"`<br> |
| `BinaryExpr` (`+`, `-`, `*`, `/`, `%`, `&`, `|`, `^`, `<<`, `>>`) | 1. Requires both operands to belong to `NUMERIC_TYPES`.

<br>

<br>2. Requires `_types_compatible(left_type, right_type)`.

 | `left_type`<br> |
| `UnaryExpr` (`!`) | Requires operand type to be `"bool"`.

 | `"bool"`<br> |
| `UnaryExpr` (`-`, `~`) | Requires operand type to belong to `NUMERIC_TYPES`.

 | `operand_type`<br> |
| `TernaryExpr` | 1. Recursively evaluates `true_expr` and `false_expr`.

<br>

<br>2. Resolves `"null"` wildcards: if one branch is `"null"`, returns the concrete type of the other branch.

<br>

<br>3. Enforces that concrete branch types match exactly.

 | Validated branch type

 |
| `FuncCall` (`mk_<struct>`) | Intercepts implicit struct constructors (`mk_Struct`). Validates that argument count and argument types match the target struct's field layout (`"null"` is permitted for pointer/struct field types).

 | `struct_name`<br> |
| `FuncCall` (`env` call) | Validates argument count and checks `_types_compatible` against formal parameter types declared in `EnvDef`.

 | `env_def.retType`<br> |
| `FuncCall` (`oracle` call) | Validates argument count and checks `_types_compatible` against formal parameters in `FunctionDef`. Passes formal parameter reference flags (`is_refer = oracle.args[i].is_refer`) when evaluating each argument.

 | `oracle.retType`<br> |
| `FuncCall` (`trace` call) | Enforces exactly 1 argument and requires `_types_compatible(arg_type, "timestep")`.

 | `trace_def.ret_type`<br> |
| `FieldAccess` | 1. Special case: if `obj_type.startswith("seq[")` and `expr.field == "length"`, short-circuits and returns `"int"` (representing a 32-bit sequence length).

<br>

<br>2. Otherwise, looks up field layout in `env.get_struct_fields(obj_type)` and verifies `expr.field` exists.

 | Field's declared type

 |
| `SeqAccess` | 1. Verifies `seq_type.startswith("seq[")`.

<br>

<br>2. Verifies `index` type belongs to `NUMERIC_TYPES`.

<br>

<br>3. Extracts inner element type via slice `seq_type[4:-1]`.

 | Inner sequence element type

 |
| `Quantifier` | Evaluates quantifier node (`forall`/`exists`).

 | `"bool"`<br> |

---

## 5. Statement & Flow Verification (`check_stmt`)

```python
def check_stmt(self, stmt: Stmt):

```

The `check_stmt` method validates imperative specification statements, enforcing type correctness, constant immutability, and substructural resource conservation across control flows.

### Statement Verification Rules Table

| AST Statement Node | Verification & Linearity Enforcement Logic |
| --- | --- |
| `AssignStmt` | 1. **Immutability Check:** If target l-value is a `VarRef`, checks `self.env.is_constant(name)`. Raises an exception if assigning to a constant.

<br>

<br>2. **Invisible Variable Check:** Checks if base variable name belongs to `self.env.invisible_vars`. If true, sets `is_invisible_assign = True`.

<br>

<br>3. **RHS Evaluation:** Calls `get_expr_type(stmt.expr, is_refer=is_invisible_assign)`. Assigning to an invisible ghost variable borrows linear resources without consuming them from $\Delta$.

<br>

<br>4. **Linear Replenishment:** If assigning to a `VarRef` whose type is a linear struct and `not is_invisible_assign`, replenishes `self.delta[base_name] = lhs_type`.

<br>

<br>5. **Type Compatibility:** Enforces `lhs_type == rhs_type`.

 |
| `AssertStmt` | 1. Takes a snapshot of `self.delta` (`snapshot = self.delta.copy()`).

<br>

<br>2. Asserts `stmt.formula` evaluates to `"bool"`.

<br>

<br>3. Restores `self.delta = snapshot` so assertions do not permanently consume linear resources.

 |
| `FactStmt` | 1. Takes a snapshot of `self.delta`.

<br>

<br>2. Asserts `stmt.formula` evaluates to `"bool"`.

<br>

<br>3. Restores `self.delta = snapshot`.

 |
| `BlockStmt` | Iterates sequentially over `stmt.statements`, invoking `check_stmt(s)` on each.

 |
| `IfStmt` | 1. Verifies `stmt.condition` evaluates to `"bool"`.

<br>

<br>2. Takes a baseline snapshot `delta_before = self.delta.copy()`.

<br>

<br>3. Evaluates `stmt.then_block`, records resulting state as `delta_then`, and restores `delta_before`.

<br>

<br>4. Evaluates `stmt.else_block` (or defaults to `delta_before` if no else branch exists), recording `delta_else`.

<br>

<br>5. **Branch Equality Check:** Enforces `delta_then == delta_else`. Raises an exception if branches consume divergent linear resources.

<br>

<br>6. Sets `self.delta = delta_then`.

 |
| `WhileStmt` | 1. Verifies `stmt.condition` evaluates to `"bool"`.

<br>

<br>2. If present, verifies `stmt.invariant` evaluates to `"bool"`.

<br>

<br>3. Takes a baseline snapshot `delta_before = self.delta.copy()`.

<br>

<br>4. Evaluates loop `stmt.body`.

<br>

<br>5. **Loop Invariance Check:** Enforces `self.delta == delta_before`. Raises an exception if a loop permanently consumes or leaks linear resources.

 |

---

## 6. Complete Program Verification Lifecycle (`check_program`)

```python
def check_program(self, program: Program):

```

The `check_program` method coordinates the complete static analysis lifecycle for a top-level `Program` AST node:

```
[1. Initialize Δ with Global Linear Structs]
                     │
                     ▼
[2. Disable Linearity & Check Pre/Postconditions == "bool"]
                     │
                     ▼
[3. Enable Linearity & Execute check_stmt() across specProgram]
                     │
                     ▼
[4. Scope Exit Check: Is len(Δ) > 0?]
          ├── YES ──► Raise Memory Leak Error (Unconsumed Linear Resources)
          └── NO  ──► ✅ Static & Linear Type Checking Proved Successful

```

1. **Global Linear Initialization:** Iterates through `self.env.variables`. For every variable whose declared type is in `self.env.linear_structs`, initializes `self.delta[var_name] = var_type`.


2. **Precondition & Postcondition Verification:** Sets `self.enforce_linearity = False` and checks that every formula in `program.preconditions` and `program.postconditions` evaluates to `"bool"`. Linearity is disabled during contract checks so specification conditions can reference linear variables without consuming them.


3. **Program Statement Analysis:** Sets `self.enforce_linearity = True` and sequentially executes `check_stmt(stmt)` on every statement in `program.specProgram`.


4. **Scope Exit Anti-Leak Verification:** Upon reaching the end of `specProgram`, checks if any linear resources remain in `self.delta` (`len(self.delta) > 0`). If unconsumed variables remain, formats a list of leaked variable names and raises a **Memory Leak Error**:


```python
raise Exception(f"Memory Leak Error: Linear variables [{leaked}] were never consumed.")

```



---

## 7. Error & Exception Catalog

The `TypeChecker` raises descriptive runtime exceptions upon detecting semantic violations:

| Exception Error Message Pattern | Trigger Condition & Description |
| --- | --- |
| `Use-After-Free Error: Linear variable '<var>' was already consumed` | Attempting to read a linear struct variable (`VarRef`) that has already been consumed from `self.delta`.

 |
| `Memory Leak Error: Linear variables [<vars>] were never consumed.` | One or more linear struct resources remain in `self.delta` at program termination.

 |
| `Linear Type Error in If/Else block` | The `then` branch and `else` branch of an `IfStmt` consumed different linear resources (`delta_then != delta_else`).

 |
| `Linear Type Error: While loop body permanently consumes resources!` | A `WhileStmt` body consumed or modified the linear resource set across an iteration (`self.delta != delta_before`).

 |
| `Type Error: Cannot assign to constant variable '<var>'` | An `AssignStmt` targets an immutable variable declared via `ConstDecl`.

 |
| `Type Error in Assignment: Cannot assign <rhs> to <lhs>` | The right-hand side expression type does not match the left-hand side variable or field type.

 |
| `Type Error: <msg> (Got '<actual>', expected '<expected>')` | Generic type assertion failure raised by `_assert_type` for predicates, assertions, conditions, or invariants.

 |
| `Type Error: '<op>' expects booleans` | A logical operator (`&&`, ` |
| `Type Error: Cannot compare '<t1>' and '<t2>'` | A relational operator (`==`, `!=`) compared incompatible types.

 |
| `Type Error in Ternary: branches have mismatched types '<t1>' and '<t2>'` | A ternary expression (`? :`) resolved to different concrete types on its true and false branches.

 |
| `Constructor mk_<name> expects <N> args, got <M>` / `<Call> expects <N> but got <M>` | A struct constructor, oracle, environment function, or trace was invoked with an incorrect number of arguments.

 |
| `Struct <type> has no field <field>` | A `FieldAccess` expression referenced a non-existent field on a struct.

 |
| `Cannot index a non-sequence type <type>` | A `SeqAccess` expression (`[idx]`) was applied to a variable that is not a sequence (`seq[...]`).

 |