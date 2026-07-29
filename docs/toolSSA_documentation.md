# TOOL Single Static Assignment & Functional Transformation Engine (`toolSSA.py`) Documentation

**Module:** `core/toolSSA.py`  
**Language:** Python 3  
**Role:** Implements `SSATransformer`, the engine responsible for converting imperative TOOL statements and mutable expressions into pure Single Static Assignment (SSA) mathematical formulas, conditional $\Phi$ (phi) nodes, functional data updates, and inductive loop transitions.

---

## 1. Architectural Overview & Single Static Assignment Principles

SMT solvers such as Z3 operate over first-order logic and pure mathematical equations; they have no concept of mutable memory, sequential execution order, or destructive variable assignments. The `SSATransformer` class bridges this semantic gap by transforming an imperative specification program into a collection of immutable mathematical constraints.


```

Imperative Statements (AssignStmt, IfStmt, WhileStmt)
│
▼
SSATransformer (toolSSA.py)
│
▼
Pure Mathematical Equations (Expr, Phi Nodes, LoopTransition)

```

### Key Functional Transformation Principles:
1. **Single Static Assignment (SSA):** Every assignment to a variable generates a new, monotonically incremented version identifier (e.g., `x := x + 1` becomes `x_1 == x_0 + 1`).
2. **Functional Data Structures:** Destructive struct field assignments and array updates are rewritten into functional constructors (`StructUpdate`, `SeqUpdate`) that return a new version of the structure while preserving the original.
3. **Conditional $\Phi$ (Phi) Merging:** Divergent execution paths in `if`/`else` branches are reconciled using ternary selection formulas that select the correct variable version based on the branching condition.
4. **Inductive Loop Havocing:** Unbounded `while` loops are transformed into a `LoopTransition` node that uses symbolic variable **Havocing** (assigning unknown arbitrary versions) to prove invariants via mathematical induction ($P(k) \implies P(k+1)$).

---

## 2. SSA Versioning & State Scoping Engine

The `SSATransformer` initializes its versioning tables and state trackers within `__init__(self, env: TypeEnvironment)`:


```

SSATransformer
├── max_versions: Dict[str, int]         # Variable -> Highest version ever allocated (never rewinds)
├── current_versions: Dict[str, int]     # Variable -> Currently active version in scope (rewinds on branches)
├── env: TypeEnvironment                 # Global symbol table and type environment
├── bound_vars: set                      # Quantifier bound variables (excluded from SSA versioning)
└── oracle_manager: OracleManager        # Contract extractor for oracle calls

```

### Core Versioning Helpers

#### `_get_current_name(self, name: str) -> str`
* **Purpose:** Retrieves the currently active SSA version of a variable for right-hand side (RHS) reads.
* **Behavior:** Checks if `name` exists in `self.current_versions`. If absent, initializes both `current_versions[name]` and `max_versions[name]` to `0`. Returns the versioned string `"name_0"`, `"name_1"`, etc.

#### `_get_next_name(self, name: str) -> str`
* **Purpose:** Allocates a brand-new SSA version for left-hand side (LHS) assignments.
* **Behavior:** Increments `self.max_versions[name]` by `1` (or sets it to `1` if uninitialized), updates `self.current_versions[name]` to match this new maximum, and returns the new versioned name.
* **Monotonicity Guarantee:** Because `max_versions` never decrements, variable names are guaranteed to be globally unique across all execution branches.

#### `_get_write_set(self, stmt: Stmt) -> set`
* **Purpose:** Recursively inspects a statement (`AssignStmt`, `BlockStmt`, `IfStmt`, `WhileStmt`) to collect all variable names modified within it.
* **Downstream Use:** Used during `WhileStmt` processing to identify which variables must be **havoced** before evaluating loop induction.

---

## 3. Expression Transformation (`transform_expr`)

```python
def transform_expr(self, node: Expr) -> Expr:

```

The `transform_expr` method traverses AST expression trees and replaces raw variable references (`VarRef`) with their currently active SSA versioned counterparts.

### Expression Transformation Rules

| Expression Node | Transformation Logic |
| --- | --- |
| `VarRef` | 1. **Bound Variable Check:** If `node.name in self.bound_vars`, returns `node` unchanged (quantifier variables are not SSA versioned).<br>

<br>2. **Constant Check:** If `self.env.is_constant(node.name)`, returns `node` unchanged (constants never mutate).<br>

<br>3. **Standard Read:** Returns `VarRef(self._get_current_name(node.name))`. |
| `Literal` | Returns `node` unchanged. |
| `BinaryExpr` / `UnaryExpr` / `TernaryExpr` | Recursively invokes `transform_expr` on all child expressions (`left`/`right`, `operand`, or `condition`/`true_expr`/`false_expr`). |
| `Quantifier` | 1. Registers `bound_var` into `self.bound_vars` to shadow global SSA variables.<br>

<br>2. Recursively transforms `node.formula`.<br>

<br>3. Removes `bound_var` from `self.bound_vars`.<br>

<br>4. Returns updated `Quantifier`. |
| `FuncCall` / `FieldAccess` / `SeqAccess` | Recursively invokes `transform_expr` on function arguments, base objects, and sequence index expressions. |

---

## 4. Imperative Statement Translation (`transform_stmt`)

```python
def transform_stmt(self, node: Stmt) -> List[Expr]:

```

The `transform_stmt` method converts an imperative specification statement into an ordered list of mathematical constraints (`List[Expr]`).

### Statement Transformation Rules Table

| Statement Node | Translation Logic & Generated Formulas |
| --- | --- |
| `AssignStmt` (`VarRef`) | 1. **Oracle Call Interception:** If the RHS is a `FuncCall` targeting an oracle (`self.env.is_oracle`), extracts `grounded_assumes` and `grounded_returns` via `OracleManager`. Appends `CallSiteCheck(ssa_assumes)` to enforce preconditions. If the oracle is non-recursive, also appends `ssa_returns` directly.<br>

<br>2. **RHS Evaluation:** Evaluates `rhs_transformed = transform_expr(node.expr)`.<br>

<br>3. **LHS Versioning:** Allocates `new_lhs = _get_next_name(name)`.<br>

<br>4. **Equality Generation:** Appends `BinaryExpr(VarRef(new_lhs), '==', rhs_transformed)`. |
| `AssignStmt` (`FieldAccess`) | Handles struct field mutations (`obj.field := expr`).<br>

<br>1. Enforces base object is a `VarRef`.<br>

<br>2. Validates field existence against `self.env.get_struct_fields(var_type)`.<br>

<br>3. Reads `old_version = VarRef(_get_current_name(base_name))`.<br>

<br>4. Allocates `new_version = VarRef(_get_next_name(base_name))`.<br>

<br>5. Generates functional update: `new_version == StructUpdate(old_version, field, rhs_transformed)`. |
| `AssignStmt` (`SeqAccess`) | Handles sequence element updates (`seq[index] := expr`).<br>

<br>1. Enforces base object is a `VarRef` of a sequence type (`seq[...]`).<br>

<br>2. Reads `old_version` and allocates `new_version`.<br>

<br>3. Transforms `index` via `transform_expr`.<br>

<br>4. Generates functional update: `new_version == SeqUpdate(old_version, transformed_idx, rhs_transformed)`. |
| `AssertStmt` | Transforms inner formula using current SSA versions and appends `AssertStmt(transformed_formula)`. |
| `FactStmt` | Transforms inner formula using current SSA versions and appends `FactStmt(transformed_formula)` directly to the timeline. |
| `BlockStmt` | Iterates through `node.statements` and extends the formula list sequentially. |
| `IfStmt` | Handles branching and generates $\Phi$ (phi) nodes (see Section 5). |
| `WhileStmt` | Handles inductive loop verification and variable havocing (see Section 6). |

---

## 5. Conditional Branching & $\Phi$ (Phi) Node Generation (`IfStmt`)

When executing an imperative `if (cond) { then_block } else { else_block }` statement, variables may mutate independently within either branch. To reconcile these divergent timelines in static assignment form, the SSA engine generates conditional **$\Phi$ (phi) nodes** using `TernaryExpr`.

```
                  [Snapshot Base Universe: x_0, y_0]
                                   │
                 ┌─────────────────┴─────────────────┐
                 ▼                                   ▼
          (cond == True)                      (cond == False)
         [Then-Universe]                     [Else-Universe]
            x_1 == ...                          y_1 == ...
                 │                                   │
                 └─────────────────┬─────────────────┘
                                   ▼
                   [Phi-Node Reconciliation Stage]
           x_2 == cond ? x_1 : x_0  |  y_2 == cond ? y_0 : y_1

```

### Step-by-Step $\Phi$ Node Generation Process:

1. **Branch Condition:** Transform `node.condition` under current SSA versions -> `cond_expr`.
2. **Snapshot Base State:** Copy `self.current_versions` -> `base_versions`.
3. **Execute Then-Block:** Translate `node.then_block`, record resulting scope -> `then_versions`.
4. **Revert & Execute Else-Block:** Reset `self.current_versions = base_versions.copy()`. Translate `node.else_block` (if present), record resulting scope -> `else_versions`.
5. **Identify Mutated Variables:** Compute union of all variables present in `then_versions` and `else_versions`.
6. **Emit $\Phi$ Equations:** For any variable `var` where `v_then != v_base` or `v_else != v_base`:
* Allocate a merged SSA version: `merged_name = _get_next_name(var)`
* Emit ternary equation:
```python
BinaryExpr(
    left=VarRef(merged_name),
    op='==',
    right=TernaryExpr(
        condition=cond_expr,
        true_expr=VarRef(f"{var}_{v_then}"),
        false_expr=VarRef(f"{var}_{v_else}")
    )
)

```





---

## 6. Inductive Loop Verification & Havocing (`WhileStmt`)

Because an SMT solver cannot statically unroll an unbounded `while (condition) { body }` loop, `SSATransformer` replaces the loop with a single **`LoopTransition`** AST node that verifies loop safety via **Mathematical Induction**.

```
[Snapshot 0: Base Case] ──► inv_pre (P(0) holds before loop entry)
         │
         ▼
[Symbolic Havocing]     ──► Increment modified vars (e.g., x_0 -> x_1) without constraints
         │
         ▼
[Snapshot 1: Inductive] ──► Assume inv_read (P(k)) and cond_read are true at arbitrary start
         │
         ▼
[Execute Loop Body]     ──► Translate body_formulas (e.g., x_2 == x_1 + 1)
         │
         ▼
[Snapshot 2: Ind. Proof]──► Prove inv_write (P(k+1)) holds at iteration end
         │
         ▼
[Rewind Scope to Start] ──► Post-loop code sees read_scope where cond_read is False

```

### Loop Induction & Havocing Lifecycle:

1. **Step 1: Base Case Proof (`inv_pre`)**
* Take snapshot `pre_loop_scope = self.current_versions.copy()`.
* Evaluate `inv_pre = self.transform_expr(node.invariant)` (defaults to `Literal("true")` if none).
* Ensures the invariant holds at iteration $0$ before loop entry.


2. **Step 2: Variable Havocing (Arbitrary $i$-th Iteration)**
* Scan loop body via `_get_write_set(node.body)` to find all modified variables.
* For every modified variable, invoke `_get_next_name(var)` to increment its version *without* assigning it a concrete equation.
* This makes modified variables completely symbolic/unconstrained (e.g., representing unknown values at iteration $i$).


3. **Step 3: Inductive Assumption ($P(k)$ at `read_scope`)**
* Take snapshot `read_scope = self.current_versions.copy()`.
* Transform `cond_read = self.transform_expr(node.condition)`.
* Transform `inv_read = self.transform_expr(node.invariant)`.
* Represents the hypothesis that the invariant and condition hold at the beginning of iteration $i$.


4. **Step 4: Execute Loop Body Transitions**
* Transform `node.body.statements` into `body_formulas`, mapping `read_scope` versions (e.g., `x_1`) to newer versions (e.g., `x_2`).


5. **Step 5: Inductive Proof ($P(k+1)$ at `write_scope`)**
* Take snapshot `write_scope = self.current_versions.copy()`.
* Transform `inv_write = self.transform_expr(node.invariant)`.
* Represents the proof obligation that after executing the body, the invariant still holds.


6. **Step 6: Scope Rewinding & Post-Loop State**
* Package all snapshots and formulas into `LoopTransition`.
* **Crucial Scope Rewind:** Set `self.current_versions = read_scope.copy()`.
* *Reasoning:* When a loop terminates, it means the loop condition was checked at `read_scope` and evaluated to `False`. Thus, any code running after the loop operates on the `read_scope` versions where `inv_read` is True and `cond_read` is False.



---

## 7. Program Transition Generation (`generate_transition_predicate`)

```python
def generate_transition_predicate(self, spec_program: List[Stmt]) -> List[Expr]:

```

The `generate_transition_predicate` method serves as the top-level driver for the SSA engine. It sequentially iterates across all imperative statements in `spec_program`, invokes `transform_stmt` on each, and flattens the resulting mathematical expressions into a unified list of formulas (`List[Expr]`) to be asserted into the Z3 solver timeline.
"""

with open("toolSSA_documentation.md", "w", encoding="utf-8") as f:
f.write(markdown_content)

print("FILE_GENERATED: toolSSA_documentation.md")

```

```text?code_stdout&code_event_index=1
FILE_GENERATED: toolSSA_documentation.md


```

# TOOL Single Static Assignment & Functional Transformation Engine (`toolSSA.py`) Documentation

**Module:** `core/toolSSA.py`

**Language:** Python 3

**Role:** Implements `SSATransformer`, the engine responsible for converting imperative TOOL statements and mutable expressions into pure Single Static Assignment (SSA) mathematical formulas, conditional $\Phi$ (phi) nodes, functional data updates, and inductive loop transitions.

---

## 1. Architectural Overview & Single Static Assignment Principles

SMT solvers such as Z3 operate over first-order logic and pure mathematical equations; they have no concept of mutable memory, sequential execution order, or destructive variable assignments. The `SSATransformer` class bridges this semantic gap by transforming an imperative specification program into a collection of immutable mathematical constraints.

```
Imperative Statements (AssignStmt, IfStmt, WhileStmt)
                       │
                       ▼
          SSATransformer (toolSSA.py)
                       │
                       ▼
Pure Mathematical Equations (Expr, Phi Nodes, LoopTransition)

```

### Key Functional Transformation Principles:

1. **Single Static Assignment (SSA):** Every assignment to a variable generates a new, monotonically incremented version identifier (e.g., `x := x + 1` becomes `x_1 == x_0 + 1`).


2. **Functional Data Structures:** Destructive struct field assignments and array updates are rewritten into functional constructors (`StructUpdate`, `SeqUpdate`) that return a new version of the structure while preserving the original.


3. **Conditional $\Phi$ (Phi) Merging:** Divergent execution paths in `if`/`else` branches are reconciled using ternary selection formulas that select the correct variable version based on the branching condition.


4. **Inductive Loop Havocing:** Unbounded `while` loops are transformed into a `LoopTransition` node that uses symbolic variable **Havocing** (assigning unknown arbitrary versions) to prove invariants via mathematical induction ($P(k) \implies P(k+1)$).



---

## 2. SSA Versioning & State Scoping Engine

The `SSATransformer` initializes its versioning tables and state trackers within `__init__(self, env: TypeEnvironment)`:

```
SSATransformer
 ├── max_versions: Dict[str, int]         # Variable -> Highest version ever allocated (never rewinds)
 ├── current_versions: Dict[str, int]     # Variable -> Currently active version in scope (rewinds on branches)
 ├── env: TypeEnvironment                 # Global symbol table and type environment
 ├── bound_vars: set                      # Quantifier bound variables (excluded from SSA versioning)
 └── oracle_manager: OracleManager        # Contract extractor for oracle calls

```

### Core Versioning Helpers

#### `_get_current_name(self, name: str) -> str`

* **Purpose:** Retrieves the currently active SSA version of a variable for right-hand side (RHS) reads.


* **Behavior:** Checks if `name` exists in `self.current_versions`. If absent, initializes both `current_versions[name]` and `max_versions[name]` to `0`. Returns the versioned string `"name_0"`, `"name_1"`, etc.



#### `_get_next_name(self, name: str) -> str`

* **Purpose:** Allocates a brand-new SSA version for left-hand side (LHS) assignments.


* **Behavior:** Increments `self.max_versions[name]` by `1` (or sets it to `1` if uninitialized), updates `self.current_versions[name]` to match this new maximum, and returns the new versioned name.


* **Monotonicity Guarantee:** Because `max_versions` never decrements, variable names are guaranteed to be globally unique across all execution branches.



#### `_get_write_set(self, stmt: Stmt) -> set`

* **Purpose:** Recursively inspects a statement (`AssignStmt`, `BlockStmt`, `IfStmt`, `WhileStmt`) to collect all variable names modified within it.


* **Downstream Use:** Used during `WhileStmt` processing to identify which variables must be **havoced** before evaluating loop induction.



---

## 3. Expression Transformation (`transform_expr`)

```python
def transform_expr(self, node: Expr) -> Expr:

```

The `transform_expr` method traverses AST expression trees and replaces raw variable references (`VarRef`) with their currently active SSA versioned counterparts.

### Expression Transformation Rules

| Expression Node | Transformation Logic |
| --- | --- |
| `VarRef` | 1. **Bound Variable Check:** If `node.name in self.bound_vars`, returns `node` unchanged (quantifier variables are not SSA versioned).

<br>

<br>2. **Constant Check:** If `self.env.is_constant(node.name)`, returns `node` unchanged (constants never mutate).

<br>

<br>3. **Standard Read:** Returns `VarRef(self._get_current_name(node.name))`.

 |
| `Literal` | Returns `node` unchanged.

 |
| `BinaryExpr` / `UnaryExpr` / `TernaryExpr` | Recursively invokes `transform_expr` on all child expressions (`left`/`right`, `operand`, or `condition`/`true_expr`/`false_expr`).

 |
| `Quantifier` | 1. Registers `bound_var` into `self.bound_vars` to shadow global SSA variables.

<br>

<br>2. Recursively transforms `node.formula`.

<br>

<br>3. Removes `bound_var` from `self.bound_vars`.

<br>

<br>4. Returns updated `Quantifier`.

 |
| `FuncCall` / `FieldAccess` / `SeqAccess` | Recursively invokes `transform_expr` on function arguments, base objects, and sequence index expressions.

 |

---

## 4. Imperative Statement Translation (`transform_stmt`)

```python
def transform_stmt(self, node: Stmt) -> List[Expr]:

```

The `transform_stmt` method converts an imperative specification statement into an ordered list of mathematical constraints (`List[Expr]`).

### Statement Transformation Rules Table

| Statement Node | Translation Logic & Generated Formulas |
| --- | --- |
| `AssignStmt` (`VarRef`) | 1. **Oracle Call Interception:** If the RHS is a `FuncCall` targeting an oracle (`self.env.is_oracle`), extracts `grounded_assumes` and `grounded_returns` via `OracleManager`. Appends `CallSiteCheck(ssa_assumes)` to enforce preconditions. If the oracle is non-recursive, also appends `ssa_returns` directly.

<br>

<br>2. **RHS Evaluation:** Evaluates `rhs_transformed = transform_expr(node.expr)`.

<br>

<br>3. **LHS Versioning:** Allocates `new_lhs = _get_next_name(name)`.

<br>

<br>4. **Equality Generation:** Appends `BinaryExpr(VarRef(new_lhs), '==', rhs_transformed)`.

 |
| `AssignStmt` (`FieldAccess`) | Handles struct field mutations (`obj.field := expr`).

<br>

<br>1. Enforces base object is a `VarRef`.

<br>

<br>2. Validates field existence against `self.env.get_struct_fields(var_type)`.

<br>

<br>3. Reads `old_version = VarRef(_get_current_name(base_name))`.

<br>

<br>4. Allocates `new_version = VarRef(_get_next_name(base_name))`.

<br>

<br>5. Generates functional update: `new_version == StructUpdate(old_version, field, rhs_transformed)`.

 |
| `AssignStmt` (`SeqAccess`) | Handles sequence element updates (`seq[index] := expr`).

<br>

<br>1. Enforces base object is a `VarRef` of a sequence type (`seq[...]`).

<br>

<br>2. Reads `old_version` and allocates `new_version`.

<br>

<br>3. Transforms `index` via `transform_expr`.

<br>

<br>4. Generates functional update: `new_version == SeqUpdate(old_version, transformed_idx, rhs_transformed)`.

 |
| `AssertStmt` | Transforms inner formula using current SSA versions and appends `AssertStmt(transformed_formula)`.

 |
| `FactStmt` | Transforms inner formula using current SSA versions and appends `FactStmt(transformed_formula)` directly to the timeline.

 |
| `BlockStmt` | Iterates through `node.statements` and extends the formula list sequentially.

 |
| `IfStmt` | Handles branching and generates $\Phi$ (phi) nodes (see Section 5).

 |
| `WhileStmt` | Handles inductive loop verification and variable havocing (see Section 6).

 |

---

## 5. Conditional Branching & $\Phi$ (Phi) Node Generation (`IfStmt`)

When executing an imperative `if (cond) { then_block } else { else_block }` statement, variables may mutate independently within either branch. To reconcile these divergent timelines in static assignment form, the SSA engine generates conditional **$\Phi$ (phi) nodes** using `TernaryExpr`.

```
                  [Snapshot Base Universe: x_0, y_0]
                                   │
                 ┌─────────────────┴─────────────────┐
                 ▼                                   ▼
          (cond == True)                      (cond == False)
         [Then-Universe]                     [Else-Universe]
            x_1 == ...                          y_1 == ...
                 │                                   │
                 └─────────────────┬─────────────────┘
                                   ▼
                   [Phi-Node Reconciliation Stage]
           x_2 == cond ? x_1 : x_0  |  y_2 == cond ? y_0 : y_1

```

### Step-by-Step $\Phi$ Node Generation Process:

1. **Branch Condition:** Transform `node.condition` under current SSA versions $\rightarrow$ `cond_expr`.


2. **Snapshot Base State:** Copy `self.current_versions` $\rightarrow$ `base_versions`.


3. **Execute Then-Block:** Translate `node.then_block`, record resulting scope $\rightarrow$ `then_versions`.


4. **Revert & Execute Else-Block:** Reset `self.current_versions = base_versions.copy()`. Translate `node.else_block` (if present), record resulting scope $\rightarrow$ `else_versions`.


5. **Identify Mutated Variables:** Compute union of all variables present in `then_versions` and `else_versions`.


6. **Emit $\Phi$ Equations:** For any variable `var` where `v_then != v_base` or `v_else != v_base`:


* Allocate a merged SSA version: `merged_name = _get_next_name(var)`

* Emit ternary equation:


```python
BinaryExpr(
    left=VarRef(merged_name),
    op='==',
    right=TernaryExpr(
        condition=cond_expr,
        true_expr=VarRef(f"{var}_{v_then}"),
        false_expr=VarRef(f"{var}_{v_else}")
    )
)

```





---

## 6. Inductive Loop Verification & Havocing (`WhileStmt`)

Because an SMT solver cannot statically unroll an unbounded `while (condition) { body }` loop, `SSATransformer` replaces the loop with a single **`LoopTransition`** AST node that verifies loop safety via **Mathematical Induction**.

```
[Snapshot 0: Base Case] ──► inv_pre (P(0) holds before loop entry)
         │
         ▼
[Symbolic Havocing]     ──► Increment modified vars (e.g., x_0 -> x_1) without constraints
         │
         ▼
[Snapshot 1: Inductive] ──► Assume inv_read (P(k)) and cond_read are true at arbitrary start
         │
         ▼
[Execute Loop Body]     ──► Translate body_formulas (e.g., x_2 == x_1 + 1)
         │
         ▼
[Snapshot 2: Ind. Proof]──► Prove inv_write (P(k+1)) holds at iteration end
         │
         ▼
[Rewind Scope to Start] ──► Post-loop code sees read_scope where cond_read is False

```

### Loop Induction & Havocing Lifecycle:

1. **Step 1: Base Case Proof (`inv_pre`)**
* Take snapshot `pre_loop_scope = self.current_versions.copy()`.


* Evaluate `inv_pre = self.transform_expr(node.invariant)` (defaults to `Literal("true")` if none).


* Ensures the invariant holds at iteration $0$ before loop entry.




2. **Step 2: Variable Havocing (Arbitrary $i$-th Iteration)**
* Scan loop body via `_get_write_set(node.body)` to find all modified variables.


* For every modified variable, invoke `_get_next_name(var)` to increment its version *without* assigning it a concrete equation.


* This makes modified variables completely symbolic/unconstrained (e.g., representing unknown values at iteration $i$).




3. **Step 3: Inductive Assumption ($P(k)$ at `read_scope`)**
* Take snapshot `read_scope = self.current_versions.copy()`.


* Transform `cond_read = self.transform_expr(node.condition)`.


* Transform `inv_read = self.transform_expr(node.invariant)`.


* Represents the hypothesis that the invariant and condition hold at the beginning of iteration $i$.




4. **Step 4: Execute Loop Body Transitions**
* Transform `node.body.statements` into `body_formulas`, mapping `read_scope` versions (e.g., `x_1`) to newer versions (e.g., `x_2`).




5. **Step 5: Inductive Proof ($P(k+1)$ at `write_scope`)**
* Take snapshot `write_scope = self.current_versions.copy()`.


* Transform `inv_write = self.transform_expr(node.invariant)`.


* Represents the proof obligation that after executing the body, the invariant still holds.




6. **Step 6: Scope Rewinding & Post-Loop State**
* Package all snapshots and formulas into `LoopTransition`.


* **Crucial Scope Rewind:** Set `self.current_versions = read_scope.copy()`.


* *Reasoning:* When a loop terminates, it means the loop condition was checked at `read_scope` and evaluated to `False`. Thus, any code running after the loop operates on the `read_scope` versions where `inv_read` is True and `cond_read` is False.





---

## 7. Program Transition Generation (`generate_transition_predicate`)

```python
def generate_transition_predicate(self, spec_program: List[Stmt]) -> List[Expr]:

```

The `generate_transition_predicate` method serves as the top-level driver for the SSA engine. It sequentially iterates across all imperative statements in `spec_program`, invokes `transform_stmt` on each, and flattens the resulting mathematical expressions into a unified list of formulas (`List[Expr]`) to be asserted into the Z3 solver timeline.