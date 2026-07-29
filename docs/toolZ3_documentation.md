# TOOL Z3 SMT Translation & Verification Engine (`toolZ3.py`) Documentation

**Module:** `core/toolZ3.py`  
**Language:** Python 3 (Z3 Python Bindings)  
**Role:** Implements `Z3Translator`, the compiler backend responsible for translating TOOL AST expressions, Algebraic Datatypes, Oracles, Environments, Temporal Traces, and Single Static Assignment (SSA) loop transitions into Z3 SMT terms and proving safety properties.

---

## 1. Architectural Overview & Design Architecture

The `Z3Translator` class translates high-level TOOL specification constructs into formal SMT-LIB2 mathematical theories within a clean Z3 context (`z3.Context()`). It acts as the final verification stage, converting typed AST nodes (`toolAst.py`) and SSA equations (`toolSSA.py`) into Z3 solver assertions.


```

```
              Typed & SSA-Transformed AST Nodes
                              │
                              ▼
                 Z3Translator (toolZ3.py)
                              │
  ┌───────────────────────────┼───────────────────────────┐
  ▼                           ▼                           ▼

```

Algebraic Datatypes       Recursive Functions          SMT-LIB2 Terms
(z3.DatatypeSortRef)    (z3.RecFunction / axioms)   (z3.ExprRef / ArraySort)
│                           │                           │
└───────────────────────────┬───────────────────────────┘
▼
Z3 SMT Solver (push / pop / check)

```

### Core Design Capabilities:
1. **Algebraic Datatype (ADT) Struct Modeling:** Models user-defined structs as Z3 Datatypes featuring mutually exclusive data (`mk_Struct`) and empty (`null_Struct`) constructors.
2. **Oracle & Trace Compilation:** Compiles recursive Oracles and temporal Traces into Z3 recursive functions (`z3.RecFunction`), while macro-expanding non-recursive Oracles inline to avoid unnecessary quantifier overhead.
3. **SMT Array Sequence Modeling:** Models sequences (`seq[T]`) as unbounded SMT arrays (`z3.ArraySort`) mapping integer indices to element sorts, with specialized uninterpreted functions to reason over sequence lengths (`Length_seq[...]`).
4. **Inductive Loop Sandboxing:** Uses solver scoping (`solver.push()` / `solver.pop()`) to independently verify loop invariants via mathematical induction without contaminating the global verification timeline.

---

## 2. Constructor & Initialization

### `__init__(self, env: TypeEnvironment)`
* **Purpose:** Initializes the Z3 translation engine, instantiates an isolated Z3 Context, sets up caching tables, and registers all user-defined structs as Z3 Algebraic Datatypes.
* **Algorithmic Workflow:**
  1. **Context Isolation:** Instantiates `self.z3_ctx = z3.Context()`, ensuring that Z3 sorts and expressions are decoupled from global Z3 state.
  2. **Cache Initialization:**
     * `self.sort_cache: Dict[str, z3.SortRef]`: Caches generated Z3 sorts by type signature string.
     * `self.var_cache: Dict[str, z3.ExprRef]`: Caches Z3 symbolic constants (`z3.Const`) by variable name.
     * `self.func_cache: Dict[str, z3.FuncDeclRef]`: Caches Z3 function declarations (`z3.Function`, `z3.RecFunction`, and length uninterpreted functions).
  3. **Recursion Bookkeeping Sets:** Initializes `self.oracle_defs_added` and `self.oracle_defs_in_progress` to prevent infinite recursion and duplicate definitions when compiling recursive oracle bodies.
  4. **Struct Registration:** Invokes `self._register_structs()` immediately upon initialization so struct sorts are available for subsequent type/sort lookups.
  5. **Oracle Manager Integration:** Instantiates `self.oracle_manager = OracleManager(self.env)` to manage contract assume/guarantee extraction.

---

## 3. Sort & Type Resolution Methods

### `get_z3_sort(self, type_name: str) -> z3.SortRef`
* **Purpose:** Converts a TOOL type signature string into its corresponding Z3 SMT sort (`z3.SortRef`) and caches the result.
* **Sort Mapping Rules:**
  * `"bool"` $\rightarrow$ `z3.BoolSort(ctx=self.z3_ctx)`
  * `"int"` $\rightarrow$ `z3.IntSort(ctx=self.z3_ctx)` (unbounded mathematical integers)
  * `"timestep"` $\rightarrow$ `z3.IntSort(ctx=self.z3_ctx)` (discrete temporal step index)
  * `"seq[T]"` $\rightarrow$ `z3.ArraySort(z3.IntSort(ctx=self.z3_ctx), inner_sort)` where `inner_sort` is recursively resolved from `T`. An array maps integer indices to element sorts.
  * *User Structs:* Evaluated from `self.sort_cache[type_name]`. Raises an exception if a struct was not registered during `_register_structs()`.

---

### `_register_structs(self)`
* **Purpose:** Translates every user-defined struct in `self.env.structs` into a Z3 Algebraic Datatype (`z3.Datatype`).
* **Algebraic Datatype (ADT) Architecture:**  
  Unlike C or Java, Z3 has no universal memory pointer or `0x00` null address. Every struct is declared as a Z3 Datatype sort with **two mutually exclusive constructors**:
  1. **The Data Constructor (`mk_<struct>`):** Declares field accessors mapping to each struct field and its corresponding Z3 sort.
  2. **The Null Constructor (`null_<struct>`):** Takes zero arguments and represents the empty/null shape of the struct.
* **Mathematical Guarantees Generated by Z3:**
  * **Mutual Exclusivity:** A struct object is mathematically proven to be either `mk_Struct(...)` OR `null_Struct()`.
  * **Recognizers:** Z3 automatically generates recognizer predicates (`is_mk_Struct(t)` and `is_null_Struct(t)`).
  * **Safe Access Enforcement:** Accessing a field accessor on a `null_Struct()` is mathematically undefined, forcing the verifier to prove non-nullity before evaluating field properties.
* **Workflow:** Creates `z3.Datatype(struct_name, ctx=self.z3_ctx)`, declares both constructors, invokes `.create()`, and stores the resulting sort in `self.sort_cache`.

---

## 4. Symbolic Constant & Variable Allocation

### `get_z3_var(self, name: str, type_name: str) -> z3.ExprRef`
* **Purpose:** Creates or retrieves a Z3 symbolic constant (`z3.Const`) for a given variable name and type.
* **Algorithmic Workflow:**
  1. Checks if `name` is present in `self.var_cache`.
  2. **Sort Validation:** If cached, checks whether `cached_var.sort() == self.get_z3_sort(type_name)`. If the sort matches, returns the cached variable.
  3. **New Allocation / Shadowing:** If absent or if the type mismatched (which occurs during parameter shadowing in recursive oracle compilation), creates a new `z3.Const(name, z3_sort)` and updates `self.var_cache[name]`.

---

## 5. Definition Body & Null Helper Methods

### `_extract_rhs(self, expr: Expr, ret_name: str) -> Expr`
* **Purpose:** Extracts the right-hand side (RHS) expression from a temporal trace equation formatted as `ret_name == expression` or `expression == ret_name`.
* **Behavior:** Checks `BinaryExpr` operands for an equality operator (`'=='`) matching `ret_name`. Returns the opposite operand. Raises an exception if the equation is malformed.

---

### `_extract_definition_body(self, expr: Expr, ret_name: str, kind: str = "definition") -> Expr`
* **Purpose:** Extracts the functional body AST expression from an oracle `Returns` clause written as `ret_name == body` or `body == ret_name`.
* **Behavior:** Inspects left and right operands of an equality formula. Returns the expression defining `ret_name`. Raises an exception if formatting is invalid.

---

### `_translate_isolated_null(self, ret_type: str) -> z3.ExprRef`
* **Purpose:** Translates a bare TOOL `null` literal when the expected return type (`ret_type`) is known.
* **Z3 API Quirk Handling:** In the Z3 Python bindings, zero-argument Datatype constructors are automatically evaluated into concrete `DatatypeRef` constant values. Calling parentheses on them (e.g., `null_constructor()`) causes a `"TypeError: 'DatatypeRef' object is not callable"`. This helper fetches `getattr(z3_sort, f"null_{ret_type}")` and casts it directly to `z3.ExprRef` without invocation.

---

## 6. Oracle & Trace Compilation Engine

### `_inline_oracle_call(self, oracle_def: FunctionDef, actual_args: List[Expr], tc: TypeChecker) -> z3.ExprRef`
* **Purpose:** Macro-expands a **non-recursive oracle** inline at the call site by substituting formal parameter variables with actual argument expressions.
* **Why Inlining is Used:** Inlining avoids generating Z3 `RecFunction` definitions and universal quantifier axioms for simple oracles, dramatically improving SMT solver performance and decidability.
* **Algorithmic Workflow:**
  1. Builds a mapping (`sub_map`) from each formal parameter name (`oracle_def.args[i].name`) to the concrete call-site AST expression (`actual_args[i]`).
  2. Extracts the return formula body from the oracle's `Returns` clause via `_extract_definition_body()`.
  3. Uses `ASTSubstitutor(sub_map).substitute(body_ast)` to produce an inlined AST expression.
  4. If the inlined AST is a bare `Literal("null")`, translates it via `_translate_isolated_null(oracle_def.retType)`; otherwise invokes `self.translate_expr(inlined_ast, tc)`.

---

### `_compile_oracle_definition(self, oracle_def: FunctionDef, tc: TypeChecker) -> z3.FuncDeclRef`
* **Purpose:** Compiles a **recursive oracle** into a Z3 recursive function declaration (`z3.RecFunction`) and attaches its mathematical body via `z3.RecAddDefinition`.
* **Algorithmic Workflow:**
  1. **Cache & Recursion Check:** If `oracle_name in self.oracle_defs_added`, returns the existing Z3 function from `self.func_cache`. If `oracle_name in self.oracle_defs_in_progress`, returns the cached function shell to allow recursive calls inside the body to resolve correctly.
  2. **Shell Creation:** Creates `z3.RecFunction(oracle_name, *domain_sorts, range_sort)` and caches it in `self.func_cache[oracle_name]`.
  3. **Body Extraction:** Extracts the AST expression body from the oracle's `Returns` clause.
  4. **Parameter Scoping & Shadowing:**
     * Saves existing entries in `self.env.variables` and `self.var_cache` for each formal parameter.
     * Injects formal parameters into `self.env.variables`.
     * Creates oracle-scoped Z3 symbolic constants named `f"__{oracle_name}_{arg_name}"` to prevent name collisions with global variables or other oracle parameters.
  5. **Body Translation & Binding:** Translates `body_ast` into a Z3 term (`z3_body`) using the scoped variables, and binds it to the function shell via `z3.RecAddDefinition(z3_func, z3_bound_vars, z3_body)`.
  6. **Scope Restoration:** Restores `self.env.variables` and `self.var_cache` to their original pre-compilation state in a `finally` block and marks `oracle_name` as added in `self.oracle_defs_added`.

---

### `_find_patterns(self, expr: z3.ExprRef, bound_vars: list) -> list`
* **Purpose:** A heuristic E-matching trigger discovery algorithm that searches a Z3 formula for array `Select` operations (`z3.Z3_OP_SELECT`) referencing quantified bound variables.
* **Why Traces & Quantifiers Need Patterns:** SMT solvers use E-matching triggers (`patterns`) to instantiate universal quantifiers (`ForAll`). Without well-chosen triggers, array axioms over sequences can cause Z3 to hang or return `unknown`.
* **Algorithmic Workflow:**
  * Inspects Z3 application nodes (`z3.is_app`). If an expression is a `Select(Array, Index)` and the index matches one of the `bound_vars`, it adds the `Select` expression to the pattern list.
  * Recursively traverses application arguments and nested quantifier bodies (`z3.is_quantifier`), returning a deduplicated list of valid trigger expressions.

---

## 7. Core Recursive AST Translator (`translate_expr`)

### `translate_expr(self, expr: ASTNode, tc: TypeChecker) -> z3.ExprRef`
* **Purpose:** The central compiler dispatch method that recursively converts any TOOL AST expression (`ASTNode`) into an evaluable Z3 SMT term (`z3.ExprRef`).
* **Detailed Function-Wise Breakdown by AST Node Kind:**

#### 1. `LoopTransition`
* **Behavior:** Pass-through handler. Returns `expr` directly without translation so the top-level test harness can pass the transition node to `verify_loop_transition()`.

#### 2. `VarRef`
* **Behavior:** Resolves base variable names (stripping numeric SSA suffixes like `_0`, `_1` to query type definitions in `self.env`), looks up the type, and returns `self.get_z3_var(expr.name, var_type)`.

#### 3. `Literal`
* **Behavior:**
  * `"true"` $\rightarrow$ `z3.BoolVal(True, ctx=self.z3_ctx)`
  * `"false"` $\rightarrow$ `z3.BoolVal(False, ctx=self.z3_ctx)`
  * Integer strings $\rightarrow$ `z3.IntVal(int(expr.value), ctx=self.z3_ctx)`

#### 4. `BinaryExpr`
* **Z3 Null Resolution Magic:** Because Z3 has no universal null, comparisons involving `Literal("null")` infer the required Algebraic Datatype sort from the opposite operand:
  * If `left` is `null` and `right` is concrete: fetches `getattr(z3_sort, f"null_{right_type}")` as `left_z3`, and translates `right`.
  * If `right` is `null` and `left` is concrete: fetches `getattr(z3_sort, f"null_{left_type}")` as `right_z3`, and translates `left`.
* **Operator Mapping:**
  * Logical: `'&&'` $\rightarrow$ `z3.And()`, `'||'` $\rightarrow$ `z3.Or()`
  * Relational: `'=='`, `'!='`, `'<'`, `'<='`, `'>'`, `'>='` $\rightarrow$ Standard Python operator overloading on Z3 terms (`==`, `!=`, `<`, etc.).
  * Arithmetic: `'+'`, `'-'`, `'*'`, `'/'`, `'%'` $\rightarrow$ Standard arithmetic operator overloading on Z3 integer terms.

#### 5. `Quantifier`
* **Behavior:**
  1. Temporarily injects `bound_var` and its type into `self.env.variables`.
  2. Generates a bounded Z3 constant via `self.get_z3_var(expr.bound_var, expr.var_type)`.
  3. Recursively translates `expr.formula` -> `inner_z3`.
  4. Discovers E-matching triggers using `self._find_patterns(inner_z3, [z3_bound_var])`.
  5. Cleans up scope injections from `self.env.variables` and `self.var_cache`.
  6. Wraps `inner_z3` in `z3.ForAll` or `z3.Exists` using the discovered patterns.

#### 6. `TernaryExpr`
* **Behavior:**
  * Evaluates condition `cond_z3 = self.translate_expr(expr.condition, tc)`.
  * **Ternary Null Resolution:** If `true_expr` is `null`, infers the Datatype null constructor from `false_expr`'s type (and vice versa).
  * Returns `z3.If(cond_z3, true_z3, false_z3)`.

#### 7. `UnaryExpr`
* **Behavior:**
  * `'!'` $\rightarrow$ `z3.Not(operand_z3)`
  * `'-'` $\rightarrow$ Arithmetic negation `-operand_z3`
  * `'~'` $\rightarrow$ Bitwise inversion `~operand_z3`

#### 8. `SeqAccess` & `SeqUpdate`
* **`SeqAccess` (`seq[idx]`):** Returns `z3.Select(seq_z3, idx_z3)`.
* **`SeqUpdate` (`seq[idx] := val`):** Returns functional array store `z3.Store(seq_z3, idx_z3, val_z3)`.

#### 9. `FuncCall`
* **Struct Constructors (`mk_<struct>`):** Intercepts calls matching constructor syntax. Evaluates arguments (resolving `'null'` arguments to the expected field's null constructor sort) and applies `dt_sort.constructor(0)(*z3_args)`.
* **Built-in `update_seq(seq, index, value)`:** Converts directly to `z3.Store(z3_arr, z3_idx, z3_val)`.
* **Built-in `mk_seq(default, v0, v1, ...)`:** Creates a constant SMT array initialized to `default` via `z3.K(z3.IntSort(ctx=ctx), default_value)`, then sequentially applies `z3.Store` for each enumerated index `0, 1, 2, ...`.
* **Environment Functions (`env`):** Compiles an uninterpreted Z3 function declaration via `z3.Function(expr.name, *domain_sorts, range_sort)` and caches it in `self.func_cache`. Returns `z3_func(*z3_args)`.
* **Oracle Functions (`oracle`):** Checks `self.oracle_manager.is_recursive(oracle_def)`. If non-recursive, calls `_inline_oracle_call()`; otherwise calls `_compile_oracle_definition()` and invokes the resulting `z3.RecFunction`.
* **Temporal Traces (`trace`):**
  * Compiles a temporal trace into a `z3.RecFunction(expr.name, timestep_sort, range_sort)`.
  * Extracts initial (`init_expr`) and step (`step_expr`) right-hand side expressions via `_extract_rhs()`.
  * Temporarily binds `time_var` to sort `"timestep"` in the environment and translates both bodies (handling bare nulls).
  * Binds a conditional definition via `z3.If(z3_bound_time == 0, z3_init, z3_step)` using `z3.RecAddDefinition`.
  * Returns `z3_func(*z3_args)`.

#### 10. `FieldAccess`
* **Sequence Length Short-Circuit (`seq.length`):**  
  SMT arrays (`ArraySort`) are infinite mathematical mappings without a native length attribute. When accessing `.length` on a sequence, the translator generates an uninterpreted function `Length_seqSort(array_term) -> IntSort` cached in `self.func_cache`. This models sequence length axiomatics without bounding array dimensions.
* **Struct Field Access (`struct.field`):** Retrieves the field accessor declaration from the Z3 Datatype sort (`getattr(z3_sort, expr.field)`) and applies it to `obj_z3`: `accessor(obj_z3)`.

#### 11. `StructUpdate`
* **Purpose:** Implements Single Static Assignment functional struct updating.
* **Behavior:** Retrieves the primary constructor (`dt_sort.constructor(0)`), iterates across all fields declared in `struct_fields`, substitutes `new_val_z3` for `expr.field`, and copies all other existing field values using their accessors (`accessor(old_obj_z3)`). Returns a new struct constructor term.

#### 12. `CallSiteCheck`
* **Behavior:** Unwraps the `CallSiteCheck` container and recursively translates the underlying assumption formula via `self.translate_expr(expr.formula, tc)`.

---

## 8. Inductive Loop Verifier

### `verify_loop_transition(self, expr: LoopTransition, tc: TypeChecker, solver: z3.Solver) -> bool`
* **Purpose:** Verifies whether a `WhileStmt` loop preserves its inductive invariant across arbitrary iterations using Z3 push/pop sandboxing and mathematical induction ($P(0) \land (P(k) \implies P(k+1))$).
* **Algorithmic Workflow:**
  1. **Translate Formulas:** Translates `inv_pre`, `inv_read`, `cond_read`, `inv_write`, and all statements in `body_formulas` into Z3 terms.
  2. **Step 1: Base Case Verification ($P(0)$)**
     * Creates an isolated solver scope: `solver.push()`.
     * Asserts the negation of the entry invariant: `solver.add(z3.Not(inv_pre))`.
     * Evaluates `solver.check()`. If `z3.sat`, a counter-example exists where the loop is entered with an invalid invariant. Logs counter-example model, pops scope, and returns `False`.
     * Pops scope: `solver.pop()`.
  3. **Step 2: Inductive Step Verification ($P(k) \land \text{cond} \implies P(k+1)$)**
     * Creates an isolated solver scope: `solver.push()`.
     * **Inductive Hypothesis:** Asserts that at the start of arbitrary iteration $k$, both the invariant and continuation condition hold: `solver.add(inv_read)` and `solver.add(cond_read)`.
     * **Execute Body:** Asserts all state transition equations in `body_formulas` representing iteration $k$.
     * **Inductive Proof Obligation:** Asserts that the invariant fails at the end of the iteration: `solver.add(z3.Not(inv_write))`.
     * Evaluates `solver.check()`. If `z3.sat`, the loop body breaks the invariant. Logs model, pops scope, and returns `False`.
     * Pops scope: `solver.pop()`.
  4. **Step 3: Post-Loop Reality Injection**
     * If both inductive checks pass, injects two established post-loop facts directly into the main solver's global timeline:
       * `solver.add(inv_read)`: The invariant still holds after loop exit.
       * `solver.add(z3.Not(cond_read))`: The loop condition is false (termination condition).
     * Returns `True`.

---

## 9. Method Signature & Functional Summary Table

| Method Name | Input Signatures | Return Type | Functional Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `env: TypeEnvironment` | `None` | Instantiates isolated Z3 context, caches, bookkeeping sets, and registers structs. |
| `get_z3_sort` | `type_name: str` | `z3.SortRef` | Converts TOOL type strings (`bool`, `int`, `seq[T]`, `timestep`, struct) into Z3 sorts. |
| `_register_structs` | `None` | `None` | Compiles struct layouts into Z3 Algebraic Datatypes (`mk_Struct` & `null_Struct`). |
| `get_z3_var` | `name: str, type_name: str` | `z3.ExprRef` | Creates or retrieves a cached Z3 symbolic constant (`z3.Const`). |
| `_extract_rhs` | `expr: Expr, ret_name: str` | `Expr` | Extracts the RHS expression from an equality formula (`ret == expr`). |
| `_extract_definition_body` | `expr: Expr, ret_name: str, kind: str` | `Expr` | Extracts the functional body AST from an oracle `Returns` contract clause. |
| `_translate_isolated_null` | `ret_type: str` | `z3.ExprRef` | Safely evaluates zero-argument Z3 Datatype null constructors without calling syntax. |
| `_inline_oracle_call` | `oracle_def: FunctionDef, actual_args: List[Expr], tc: TypeChecker` | `z3.ExprRef` | Macro-expands non-recursive oracle calls inline using `ASTSubstitutor`. |
| `_compile_oracle_definition` | `oracle_def: FunctionDef, tc: TypeChecker` | `z3.FuncDeclRef` | Compiles recursive oracles into `z3.RecFunction` declarations with scoped parameter names. |
| `_find_patterns` | `expr: z3.ExprRef, bound_vars: list` | `list` | Discovers array `Select` expressions over quantified variables for SMT E-matching triggers. |
| `translate_expr` | `expr: ASTNode, tc: TypeChecker` | `z3.ExprRef` | Recursive compiler method dispatching AST nodes into evaluable Z3 SMT terms. |
| `verify_loop_transition` | `expr: LoopTransition, tc: TypeChecker, solver: z3.Solver` | `bool` | Verifies while loops via mathematical induction using Z3 push/pop sandboxing. |
"""

with open("toolZ3_documentation.md", "w", encoding="utf-8") as f:
    f.write(markdown_content)

print("FILE_GENERATED: toolZ3_documentation.md")


```

```text
FILE_GENERATED: toolZ3_documentation.md


```

I have generated and saved the standalone Markdown documentation file for `core/toolZ3.py` titled **`toolZ3_documentation.md`**. Below is the complete, unabridged technical documentation, structured **function-wise** with an in-depth breakdown of each method in `Z3Translator`.

# TOOL Z3 SMT Translation & Verification Engine (`toolZ3.py`) Documentation

**Module:** `core/toolZ3.py`

**Language:** Python 3 (Z3 Python Bindings)

**Role:** Implements `Z3Translator`, the compiler backend responsible for translating TOOL AST expressions, Algebraic Datatypes, Oracles, Environments, Temporal Traces, and Single Static Assignment (SSA) loop transitions into Z3 SMT terms and proving safety properties.

---

## 1. Architectural Overview & Design Architecture

The `Z3Translator` class translates high-level TOOL specification constructs into formal SMT-LIB2 mathematical theories within a clean Z3 context (`z3.Context()`). It acts as the final verification stage, converting typed AST nodes (`toolAst.py`) and SSA equations (`toolSSA.py`) into Z3 solver assertions.

```
                  Typed & SSA-Transformed AST Nodes
                                  │
                                  ▼
                     Z3Translator (toolZ3.py)
                                  │
      ┌───────────────────────────┼───────────────────────────┐
      ▼                           ▼                           ▼
Algebraic Datatypes       Recursive Functions          SMT-LIB2 Terms
 (z3.DatatypeSortRef)    (z3.RecFunction / axioms)   (z3.ExprRef / ArraySort)
      │                           │                           │
      └───────────────────────────┬───────────────────────────┘
                                  ▼
                  Z3 SMT Solver (push / pop / check)

```

### Core Design Capabilities:

1. **Algebraic Datatype (ADT) Struct Modeling:** Models user-defined structs as Z3 Datatypes featuring mutually exclusive data (`mk_Struct`) and empty (`null_Struct`) constructors.


2. **Oracle & Trace Compilation:** Compiles recursive Oracles and temporal Traces into Z3 recursive functions (`z3.RecFunction`), while macro-expanding non-recursive Oracles inline to avoid unnecessary quantifier overhead.


3. **SMT Array Sequence Modeling:** Models sequences (`seq[T]`) as unbounded SMT arrays (`z3.ArraySort`) mapping integer indices to element sorts, with specialized uninterpreted functions to reason over sequence lengths (`Length_seq[...]`).


4. **Inductive Loop Sandboxing:** Uses solver scoping (`solver.push()` / `solver.pop()`) to independently verify loop invariants via mathematical induction without contaminating the global verification timeline.



---

## 2. Constructor & Initialization

### `__init__(self, env: TypeEnvironment)`

* **Purpose:** Initializes the Z3 translation engine, instantiates an isolated Z3 Context, sets up caching tables, and registers all user-defined structs as Z3 Algebraic Datatypes.


* **Algorithmic Workflow:**
1. **Context Isolation:** Instantiates `self.z3_ctx = z3.Context()`, ensuring that Z3 sorts and expressions are decoupled from global Z3 state.


2. **Cache Initialization:**
* `self.sort_cache: Dict[str, z3.SortRef]`: Caches generated Z3 sorts by type signature string.


* `self.var_cache: Dict[str, z3.ExprRef]`: Caches Z3 symbolic constants (`z3.Const`) by variable name.


* `self.func_cache: Dict[str, z3.FuncDeclRef]`: Caches Z3 function declarations (`z3.Function`, `z3.RecFunction`, and length uninterpreted functions).




3. **Recursion Bookkeeping Sets:** Initializes `self.oracle_defs_added` and `self.oracle_defs_in_progress` to prevent infinite recursion and duplicate definitions when compiling recursive oracle bodies.


4. **Struct Registration:** Invokes `self._register_structs()` immediately upon initialization so struct sorts are available for subsequent type/sort lookups.


5. **Oracle Manager Integration:** Instantiates `self.oracle_manager = OracleManager(self.env)` to manage contract assume/guarantee extraction.





---

## 3. Sort & Type Resolution Methods

### `get_z3_sort(self, type_name: str) -> z3.SortRef`

* **Purpose:** Converts a TOOL type signature string into its corresponding Z3 SMT sort (`z3.SortRef`) and caches the result.


* **Sort Mapping Rules:**
* `"bool"` $\rightarrow$ `z3.BoolSort(ctx=self.z3_ctx)`

* `"int"` $\rightarrow$ `z3.IntSort(ctx=self.z3_ctx)` (unbounded mathematical integers)


* `"timestep"` $\rightarrow$ `z3.IntSort(ctx=self.z3_ctx)` (discrete temporal step index)


* `"seq[T]"` $\rightarrow$ `z3.ArraySort(z3.IntSort(ctx=self.z3_ctx), inner_sort)` where `inner_sort` is recursively resolved from `T`. An array maps integer indices to element sorts.


* *User Structs:* Evaluated from `self.sort_cache[type_name]`. Raises an exception if a struct was not registered during `_register_structs()`.





---

### `_register_structs(self)`

* **Purpose:** Translates every user-defined struct in `self.env.structs` into a Z3 Algebraic Datatype (`z3.Datatype`).


* **Algebraic Datatype (ADT) Architecture:**
Unlike C or Java, Z3 has no universal memory pointer or `0x00` null address. Every struct is declared as a Z3 Datatype sort with **two mutually exclusive constructors**:


1. **The Data Constructor (`mk_<struct>`):** Declares field accessors mapping to each struct field and its corresponding Z3 sort.


2. **The Null Constructor (`null_<struct>`):** Takes zero arguments and represents the empty/null shape of the struct.




* **Mathematical Guarantees Generated by Z3:**
* **Mutual Exclusivity:** A struct object is mathematically proven to be either `mk_Struct(...)` OR `null_Struct()`.


* **Recognizers:** Z3 automatically generates recognizer predicates (`is_mk_Struct(t)` and `is_null_Struct(t)`).


* **Safe Access Enforcement:** Accessing a field accessor on a `null_Struct()` is mathematically undefined, forcing the verifier to prove non-nullity before evaluating field properties.




* **Workflow:** Creates `z3.Datatype(struct_name, ctx=self.z3_ctx)`, declares both constructors, invokes `.create()`, and stores the resulting sort in `self.sort_cache`.



---

## 4. Symbolic Constant & Variable Allocation

### `get_z3_var(self, name: str, type_name: str) -> z3.ExprRef`

* **Purpose:** Creates or retrieves a Z3 symbolic constant (`z3.Const`) for a given variable name and type.


* **Algorithmic Workflow:**
1. Checks if `name` is present in `self.var_cache`.


2. **Sort Validation:** If cached, checks whether `cached_var.sort() == self.get_z3_sort(type_name)`. If the sort matches, returns the cached variable.


3. **New Allocation / Shadowing:** If absent or if the type mismatched (which occurs during parameter shadowing in recursive oracle compilation), creates a new `z3.Const(name, z3_sort)` and updates `self.var_cache[name]`.





---

## 5. Definition Body & Null Helper Methods

### `_extract_rhs(self, expr: Expr, ret_name: str) -> Expr`

* **Purpose:** Extracts the right-hand side (RHS) expression from a temporal trace equation formatted as `ret_name == expression` or `expression == ret_name`.


* **Behavior:** Checks `BinaryExpr` operands for an equality operator (`'=='`) matching `ret_name`. Returns the opposite operand. Raises an exception if the equation is malformed.



---

### `_extract_definition_body(self, expr: Expr, ret_name: str, kind: str = "definition") -> Expr`

* **Purpose:** Extracts the functional body AST expression from an oracle `Returns` clause written as `ret_name == body` or `body == ret_name`.


* **Behavior:** Inspects left and right operands of an equality formula. Returns the expression defining `ret_name`. Raises an exception if formatting is invalid.



---

### `_translate_isolated_null(self, ret_type: str) -> z3.ExprRef`

* **Purpose:** Translates a bare TOOL `null` literal when the expected return type (`ret_type`) is known.


* **Z3 API Quirk Handling:** In the Z3 Python bindings, zero-argument Datatype constructors are automatically evaluated into concrete `DatatypeRef` constant values. Calling parentheses on them (e.g., `null_constructor()`) causes a `"TypeError: 'DatatypeRef' object is not callable"`. This helper fetches `getattr(z3_sort, f"null_{ret_type}")` and casts it directly to `z3.ExprRef` without invocation.



---

## 6. Oracle & Trace Compilation Engine

### `_inline_oracle_call(self, oracle_def: FunctionDef, actual_args: List[Expr], tc: TypeChecker) -> z3.ExprRef`

* **Purpose:** Macro-expands a **non-recursive oracle** inline at the call site by substituting formal parameter variables with actual argument expressions.


* **Why Inlining is Used:** Inlining avoids generating Z3 `RecFunction` definitions and universal quantifier axioms for simple oracles, dramatically improving SMT solver performance and decidability.


* **Algorithmic Workflow:**
1. Builds a mapping (`sub_map`) from each formal parameter name (`oracle_def.args[i].name`) to the concrete call-site AST expression (`actual_args[i]`).


2. Extracts the return formula body from the oracle's `Returns` clause via `_extract_definition_body()`.


3. Uses `ASTSubstitutor(sub_map).substitute(body_ast)` to produce an inlined AST expression.


4. If the inlined AST is a bare `Literal("null")`, translates it via `_translate_isolated_null(oracle_def.retType)`; otherwise invokes `self.translate_expr(inlined_ast, tc)`.





---

### `_compile_oracle_definition(self, oracle_def: FunctionDef, tc: TypeChecker) -> z3.FuncDeclRef`

* **Purpose:** Compiles a **recursive oracle** into a Z3 recursive function declaration (`z3.RecFunction`) and attaches its mathematical body via `z3.RecAddDefinition`.


* **Algorithmic Workflow:**
1. **Cache & Recursion Check:** If `oracle_name in self.oracle_defs_added`, returns the existing Z3 function from `self.func_cache`. If `oracle_name in self.oracle_defs_in_progress`, returns the cached function shell to allow recursive calls inside the body to resolve correctly.


2. **Shell Creation:** Creates `z3.RecFunction(oracle_name, *domain_sorts, range_sort)` and caches it in `self.func_cache[oracle_name]`.


3. **Body Extraction:** Extracts the AST expression body from the oracle's `Returns` clause.


4. **Parameter Scoping & Shadowing:**
* Saves existing entries in `self.env.variables` and `self.var_cache` for each formal parameter.


* Injects formal parameters into `self.env.variables`.


* Creates oracle-scoped Z3 symbolic constants named `f"__{oracle_name}_{arg_name}"` to prevent name collisions with global variables or other oracle parameters.




5. **Body Translation & Binding:** Translates `body_ast` into a Z3 term (`z3_body`) using the scoped variables, and binds it to the function shell via `z3.RecAddDefinition(z3_func, z3_bound_vars, z3_body)`.


6. **Scope Restoration:** Restores `self.env.variables` and `self.var_cache` to their original pre-compilation state in a `finally` block and marks `oracle_name` as added in `self.oracle_defs_added`.





---

### `_find_patterns(self, expr: z3.ExprRef, bound_vars: list) -> list`

* **Purpose:** A heuristic E-matching trigger discovery algorithm that searches a Z3 formula for array `Select` operations (`z3.Z3_OP_SELECT`) referencing quantified bound variables.


* **Why Traces & Quantifiers Need Patterns:** SMT solvers use E-matching triggers (`patterns`) to instantiate universal quantifiers (`ForAll`). Without well-chosen triggers, array axioms over sequences can cause Z3 to hang or return `unknown`.
* **Algorithmic Workflow:**
* Inspects Z3 application nodes (`z3.is_app`). If an expression is a `Select(Array, Index)` and the index matches one of the `bound_vars`, it adds the `Select` expression to the pattern list.


* Recursively traverses application arguments and nested quantifier bodies (`z3.is_quantifier`), returning a deduplicated list of valid trigger expressions.





---

## 7. Core Recursive AST Translator (`translate_expr`)

### `translate_expr(self, expr: ASTNode, tc: TypeChecker) -> z3.ExprRef`

* **Purpose:** The central compiler dispatch method that recursively converts any TOOL AST expression (`ASTNode`) into an evaluable Z3 SMT term (`z3.ExprRef`).


* **Detailed Function-Wise Breakdown by AST Node Kind:**

#### 1. `LoopTransition`

* **Behavior:** Pass-through handler. Returns `expr` directly without translation so the top-level test harness can pass the transition node to `verify_loop_transition()`.



#### 2. `VarRef`

* **Behavior:** Resolves base variable names (stripping numeric SSA suffixes like `_0`, `_1` to query type definitions in `self.env`), looks up the type, and returns `self.get_z3_var(expr.name, var_type)`.



#### 3. `Literal`

* **Behavior:**
* `"true"` $\rightarrow$ `z3.BoolVal(True, ctx=self.z3_ctx)`

* `"false"` $\rightarrow$ `z3.BoolVal(False, ctx=self.z3_ctx)`

* Integer strings $\rightarrow$ `z3.IntVal(int(expr.value), ctx=self.z3_ctx)`




#### 4. `BinaryExpr`

* **Z3 Null Resolution Magic:** Because Z3 has no universal null, comparisons involving `Literal("null")` infer the required Algebraic Datatype sort from the opposite operand:


* If `left` is `null` and `right` is concrete: fetches `getattr(z3_sort, f"null_{right_type}")` as `left_z3`, and translates `right`.


* If `right` is `null` and `left` is concrete: fetches `getattr(z3_sort, f"null_{left_type}")` as `right_z3`, and translates `left`.




* **Operator Mapping:**
* Logical: `'&&'` $\rightarrow$ `z3.And()`, `'||'` $\rightarrow$ `z3.Or()`

* Relational: `'=='`, `'!='`, `'<'`, `'<='`, `'>'`, `'>='` $\rightarrow$ Standard Python operator overloading on Z3 terms (`==`, `!=`, `<`, etc.).


* Arithmetic: `'+'`, `'-'`, `'*'`, `'/'`, `'%'` $\rightarrow$ Standard arithmetic operator overloading on Z3 integer terms.





#### 5. `Quantifier`

* **Behavior:**
1. Temporarily injects `bound_var` and its type into `self.env.variables`.


2. Generates a bounded Z3 constant via `self.get_z3_var(expr.bound_var, expr.var_type)`.


3. Recursively translates `expr.formula` $\rightarrow$ `inner_z3`.


4. Discovers E-matching triggers using `self._find_patterns(inner_z3, [z3_bound_var])`.


5. Cleans up scope injections from `self.env.variables` and `self.var_cache`.


6. Wraps `inner_z3` in `z3.ForAll` or `z3.Exists` using the discovered patterns.





#### 6. `TernaryExpr`

* **Behavior:**
* Evaluates condition `cond_z3 = self.translate_expr(expr.condition, tc)`.


* **Ternary Null Resolution:** If `true_expr` is `null`, infers the Datatype null constructor from `false_expr`'s type (and vice versa).


* Returns `z3.If(cond_z3, true_z3, false_z3)`.





#### 7. `UnaryExpr`

* **Behavior:**
* `'!'` $\rightarrow$ `z3.Not(operand_z3)`

* `'-'` $\rightarrow$ Arithmetic negation `-operand_z3`

* `'~'` $\rightarrow$ Bitwise inversion `~operand_z3`




#### 8. `SeqAccess` & `SeqUpdate`

* **`SeqAccess` (`seq[idx]`):** Returns `z3.Select(seq_z3, idx_z3)`.


* **`SeqUpdate` (`seq[idx] := val`):** Returns functional array store `z3.Store(seq_z3, idx_z3, val_z3)`.



#### 9. `FuncCall`

* **Struct Constructors (`mk_<struct>`):** Intercepts calls matching constructor syntax. Evaluates arguments (resolving `'null'` arguments to the expected field's null constructor sort) and applies `dt_sort.constructor(0)(*z3_args)`.


* **Built-in `update_seq(seq, index, value)`:** Converts directly to `z3.Store(z3_arr, z3_idx, z3_val)`.


* **Built-in `mk_seq(default, v0, v1, ...)`:** Creates a constant SMT array initialized to `default` via `z3.K(z3.IntSort(ctx=ctx), default_value)`, then sequentially applies `z3.Store` for each enumerated index `0, 1, 2, ...`.


* **Environment Functions (`env`):** Compiles an uninterpreted Z3 function declaration via `z3.Function(expr.name, *domain_sorts, range_sort)` and caches it in `self.func_cache`. Returns `z3_func(*z3_args)`.


* **Oracle Functions (`oracle`):** Checks `self.oracle_manager.is_recursive(oracle_def)`. If non-recursive, calls `_inline_oracle_call()`; otherwise calls `_compile_oracle_definition()` and invokes the resulting `z3.RecFunction`.


* **Temporal Traces (`trace`):**
* Compiles a temporal trace into a `z3.RecFunction(expr.name, timestep_sort, range_sort)`.


* Extracts initial (`init_expr`) and step (`step_expr`) right-hand side expressions via `_extract_rhs()`.


* Temporarily binds `time_var` to sort `"timestep"` in the environment and translates both bodies (handling bare nulls).


* Binds a conditional definition via `z3.If(z3_bound_time == 0, z3_init, z3_step)` using `z3.RecAddDefinition`.


* Returns `z3_func(*z3_args)`.





#### 10. `FieldAccess`

* **Sequence Length Short-Circuit (`seq.length`):**
SMT arrays (`ArraySort`) are infinite mathematical mappings without a native length attribute. When accessing `.length` on a sequence, the translator generates an uninterpreted function `Length_seqSort(array_term) -> IntSort` cached in `self.func_cache`. This models sequence length axiomatics without bounding array dimensions.


* **Struct Field Access (`struct.field`):** Retrieves the field accessor declaration from the Z3 Datatype sort (`getattr(z3_sort, expr.field)`) and applies it to `obj_z3`: `accessor(obj_z3)`.



#### 11. `StructUpdate`

* **Purpose:** Implements Single Static Assignment functional struct updating.


* **Behavior:** Retrieves the primary constructor (`dt_sort.constructor(0)`), iterates across all fields declared in `struct_fields`, substitutes `new_val_z3` for `expr.field`, and copies all other existing field values using their accessors (`accessor(old_obj_z3)`). Returns a new struct constructor term.



#### 12. `CallSiteCheck`

* **Behavior:** Unwraps the `CallSiteCheck` container and recursively translates the underlying assumption formula via `self.translate_expr(expr.formula, tc)`.



---

## 8. Inductive Loop Verifier

### `verify_loop_transition(self, expr: LoopTransition, tc: TypeChecker, solver: z3.Solver) -> bool`

* **Purpose:** Verifies whether a `WhileStmt` loop preserves its inductive invariant across arbitrary iterations using Z3 push/pop sandboxing and mathematical induction ($P(0) \land (P(k) \implies P(k+1))$).


* **Algorithmic Workflow:**
1. **Translate Formulas:** Translates `inv_pre`, `inv_read`, `cond_read`, `inv_write`, and all statements in `body_formulas` into Z3 terms.


2. **Step 1: Base Case Verification ($P(0)$)**
* Creates an isolated solver scope: `solver.push()`.


* Asserts the negation of the entry invariant: `solver.add(z3.Not(inv_pre))`.


* Evaluates `solver.check()`. If `z3.sat`, a counter-example exists where the loop is entered with an invalid invariant. Logs counter-example model, pops scope, and returns `False`.


* Pops scope: `solver.pop()`.




3. **Step 2: Inductive Step Verification ($P(k) \land \text{cond} \implies P(k+1)$)**
* Creates an isolated solver scope: `solver.push()`.


* **Inductive Hypothesis:** Asserts that at the start of arbitrary iteration $k$, both the invariant and continuation condition hold: `solver.add(inv_read)` and `solver.add(cond_read)`.


* **Execute Body:** Asserts all state transition equations in `body_formulas` representing iteration $k$.


* **Inductive Proof Obligation:** Asserts that the invariant fails at the end of the iteration: `solver.add(z3.Not(inv_write))`.


* Evaluates `solver.check()`. If `z3.sat`, the loop body breaks the invariant. Logs model, pops scope, and returns `False`.


* Pops scope: `solver.pop()`.




4. **Step 3: Post-Loop Reality Injection**
* If both inductive checks pass, injects two established post-loop facts directly into the main solver's global timeline:


* `solver.add(inv_read)`: The invariant still holds after loop exit.


* `solver.add(z3.Not(cond_read))`: The loop condition is false (termination condition).




* Returns `True`.







---

## 9. Method Signature & Functional Summary Table

| Method Name | Input Signatures | Return Type | Functional Description |
| --- | --- | --- | --- |
| `__init__` | `env: TypeEnvironment` | `None` | Instantiates isolated Z3 context, caches, bookkeeping sets, and registers structs.

 |
| `get_z3_sort` | `type_name: str` | `z3.SortRef` | Converts TOOL type strings (`bool`, `int`, `seq[T]`, `timestep`, struct) into Z3 sorts.

 |
| `_register_structs` | `None` | `None` | Compiles struct layouts into Z3 Algebraic Datatypes (`mk_Struct` & `null_Struct`).

 |
| `get_z3_var` | `name: str, type_name: str` | `z3.ExprRef` | Creates or retrieves a cached Z3 symbolic constant (`z3.Const`).

 |
| `_extract_rhs` | `expr: Expr, ret_name: str` | `Expr` | Extracts the RHS expression from an equality formula (`ret == expr`).

 |
| `_extract_definition_body` | `expr: Expr, ret_name: str, kind: str` | `Expr` | Extracts the functional body AST from an oracle `Returns` contract clause.

 |
| `_translate_isolated_null` | `ret_type: str` | `z3.ExprRef` | Safely evaluates zero-argument Z3 Datatype null constructors without calling syntax.

 |
| `_inline_oracle_call` | `oracle_def: FunctionDef, actual_args: List[Expr], tc: TypeChecker` | `z3.ExprRef` | Macro-expands non-recursive oracle calls inline using `ASTSubstitutor`.

 |
| `_compile_oracle_definition` | `oracle_def: FunctionDef, tc: TypeChecker` | `z3.FuncDeclRef` | Compiles recursive oracles into `z3.RecFunction` declarations with scoped parameter names.

 |
| `_find_patterns` | `expr: z3.ExprRef, bound_vars: list` | `list` | Discovers array `Select` expressions over quantified variables for SMT E-matching triggers.

 |
| `translate_expr` | `expr: ASTNode, tc: TypeChecker` | `z3.ExprRef` | Recursive compiler method dispatching AST nodes into evaluable Z3 SMT terms.

 |
| `verify_loop_transition` | `expr: LoopTransition, tc: TypeChecker, solver: z3.Solver` | `bool` | Verifies while loops via mathematical induction using Z3 push/pop sandboxing.

 |