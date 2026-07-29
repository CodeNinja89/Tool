# TOOL Oracle Contract Manager & AST Substitution Engine (`toolOracles.py`) Documentation

**Module:** `core/toolOracles.py`  
**Language:** Python 3  
**Role:** Implements `ASTSubstitutor` and `OracleManager`, providing formal parameter grounding, variable capture prevention, self-recursion detection, and assume/guarantee contract extraction for TOOL axiomatic Oracle functions.

---

## 1. Architectural Overview & Oracle Axiom Mechanics

In the Typed Oracle Oriented Language (TOOL), an **Oracle** is an axiomatic specification function defined with explicit assume/guarantee contracts (`assumes` and `returns` clauses). When an imperative statement or expression invokes an oracle via `FuncCall`, the verification pipeline must mathematically connect the oracle's formal definition to the specific concrete arguments passed at the call site.


```

```
   [Oracle Formal Definition: oracle f(arg_1, ...) -> res]
                     │
                     │ (Formal Parameters -> Concrete Arguments)
                     │ (retName -> Call-Site FuncCall)
                     ▼
    [OracleManager.extract_contract(func_call)]
                     │
                     ▼
    [ASTSubstitutor.substitute(returns_expr / assumes_expr)]
                     │
                     ▼

```

[Grounded Contract Tuple: (grounded_assumes, grounded_returns)]

```

### Key Responsibilities:
1. **Contract Grounding (`extract_contract`):** Maps formal parameter names to concrete call-site arguments and replaces occurrences of the oracle's return variable (`retName`) with the actual `FuncCall` AST node.
2. **Variable Capture Protection (`ASTSubstitutor`):** Recursively traverses contract formulas to apply substitutions while safely shadowing first-order quantifier bound variables (`forall`/`exists`), preventing accidental variable capture.
3. **Recursion Detection (`is_recursive`):** Analyzes oracle bodies to determine whether an oracle is self-recursive, signaling to downstream Z3 translation whether to compile the function using `z3.RecFunction` or inline expansion.

---

## 2. AST Substitution Engine (`ASTSubstitutor`)

```python
class ASTSubstitutor:
    def __init__(self, substitution_map: Dict[str, Expr]):
        self.sub_map = substitution_map

```

The `ASTSubstitutor` class performs deep-copy transformations on AST expressions (`Expr`), replacing variable references (`VarRef`) whose identifiers match keys in `self.sub_map` with their corresponding mapped AST expressions.

### Quantifier Shadowing & Capture Prevention

When substituting variables inside first-order logic quantifiers (`Quantifier`), the substitutor enforces lexical scoping rules: if a quantifier binds a variable (`node.bound_var`) that has the same name as an entry in `self.sub_map`, the mapping is temporarily removed (shadowed) before recursing into `node.formula`, and restored immediately after.

```python
# Quantifier Shadowing Logic
shadowed_val = None
if node.bound_var in self.sub_map:
    shadowed_val = self.sub_map.pop(node.bound_var)

new_formula = self.substitute(node.formula)

if shadowed_val is not None:
    self.sub_map[node.bound_var] = shadowed_val

```

* **Why this is critical:** Without shadowing, if an oracle formal parameter is named `i`, and an inner `forall i: int . footprint[i] == 0` quantifier also uses `i`, a naive substitution would replace the quantified bound variable `i` with the caller's concrete argument, destroying the mathematical validity of the formula.

### Recursive AST Substitution Rules Table

| AST Expression Node | Transformation & Substitution Logic |
| --- | --- |
| `VarRef` | Checks if `node.name in self.sub_map`. If present, returns `self.sub_map[node.name]`; otherwise returns `node` unchanged. |
| `Literal` | Returns `node` unchanged (literals contain no variable references). |
| `BinaryExpr` | Recursively invokes `substitute` on `node.left` and `node.right`, returning a new `BinaryExpr(left, op, right)`. |
| `UnaryExpr` | Recursively invokes `substitute` on `node.operand`, returning a new `UnaryExpr(op, operand)`. |
| `TernaryExpr` | Recursively invokes `substitute` on `node.condition`, `node.true_expr`, and `node.false_expr`. |
| `FuncCall` | Recursively invokes `substitute` across every argument in `node.args`, returning a new `FuncCall(name, args)`. |
| `SeqAccess` | Recursively invokes `substitute` on both `node.seq_obj` and `node.index`. |
| `FieldAccess` | Recursively invokes `substitute` on `node.obj` while preserving `node.field`. |
| `Quantifier` | Applies temporary `self.sub_map` shadowing for `node.bound_var`, recursively substitutes inside `node.formula`, restores the map, and returns a new `Quantifier`. |

---

## 3. Oracle Contract Management (`OracleManager`)

```python
class OracleManager:
    def __init__(self, env: TypeEnvironment) -> None:
        self.env = env

```

The `OracleManager` interfaces directly with `TypeEnvironment` to inspect registered `FunctionDef` oracle signatures and extract call-site-grounded assume/guarantee contracts.

---

### Recursion Detection (`is_recursive`)

```python
def is_recursive(self, oracle_def: FunctionDef) -> bool:

```

* **Purpose:** Inspects an oracle definition's contract clauses (`Assume` and `Returns`) to detect whether the oracle invokes itself recursively.
* **Algorithm:** Implements a nested recursive helper function, `check_node(node: ASTNode) -> bool`, that walks every expression tree inside `oracle_def.clauses`:
* Returns `True` if it encounters a `FuncCall` where `node.name == oracle_def.name`.
* Recursively checks child expressions of `FuncCall`, `BinaryExpr`, `UnaryExpr`, `TernaryExpr`, `Quantifier`, `FieldAccess`, and `SeqAccess`.


* **Downstream Integration:** In `toolSSA.py` and `toolZ3.py`, if `is_recursive()` returns `False`, non-recursive oracle calls can be safely macro-expanded or inlined at call sites without requiring Z3 recursive function axioms.

---

### Contract Extraction & Grounding (`extract_contract`)

```python
def extract_contract(self, func_call: FuncCall) -> tuple[Optional[Expr], Expr]:

```

The `extract_contract` method is the core operational bridge of `OracleManager`. Given a concrete `FuncCall` AST node representing an oracle invocation, it retrieves the oracle's formal contract and substitutes formal symbols with concrete call-site expressions.

#### Step-by-Step Contract Grounding Workflow:

```
[1. Lookup Oracle Definition in self.env.oracles]
                      │
                      ▼
[2. Validate Argument Count: len(args) == len(formal_args)]
                      │
                      ▼
[3. Build Substitution Map (sub_map)]
  ├── formal_arg_1.name  ──► func_call.args[0]
  ├── formal_arg_n.name  ──► func_call.args[n-1]
  └── oracle_def.retName ──► func_call (The Call-Site AST Node itself)
                      │
                      ▼
[4. Extract Assume & Returns Contract Clauses]
                      │
                      ▼
[5. Run ASTSubstitutor.substitute() on Both Clauses]
                      │
                      ▼
[Return Tuple: (grounded_assumes, grounded_returns)]

```

1. **Oracle Definition Lookup:** Retrieves `oracle_def = self.env.oracles[func_call.name]`. Raises an exception if the oracle is undefined.
2. **Arity Validation:** Enforces that `len(func_call.args) == len(oracle_def.args)`. Raises an exception if argument counts mismatch.
3. **Parameter Mapping:** Iterates over formal parameters (`oracle_def.args`), mapping each formal parameter name to the concrete call-site AST expression:
```python
sub_map[formal_arg.name] = func_call.args[i]

```


4. **Return Value Binding:** Maps the oracle's declared return variable (`oracle_def.retName`) directly to the `func_call` AST node:
```python
sub_map[oracle_def.retName] = func_call

```


* *Example:* If an oracle is defined as `oracle is_acyclic(seq: seq[int]) -> res: bool { returns res == ...; }`, calling `is_acyclic(footprint_1)` maps formal parameter `"seq"` to `VarRef("footprint_1")` and formal return variable `"res"` to `FuncCall("is_acyclic", [VarRef("footprint_1")])`.


5. **Clause Unpacking:** Scans `oracle_def.clauses` to separate the `Assume` formula (`assumes_expr`) and `Returns` formula (`returns_expr`).
6. **Mandatory Return Check:** Enforces that `returns_expr` is not `None`. Raises an exception if an oracle lacks a `returns` clause.
7. **AST Substitution:** Instantiates `ASTSubstitutor(sub_map)` and executes `.substitute()` on both formulas, producing `(grounded_assumes, grounded_returns)`.

---

## 4. Complete Method & Error Reference Table

| Method / Class | Input Parameters | Return Type | Exception / Error Condition |
| --- | --- | --- | --- |
| `ASTSubstitutor.substitute` | `node: Expr` | `Expr` | None |
| `OracleManager.is_recursive` | `oracle_def: FunctionDef` | `bool` | None |
| `OracleManager.extract_contract` | `func_call: FuncCall` | `tuple[Optional[Expr], Expr]` | 1. Raises `Exception(f"Oralce {name} is not defined!")` if missing from environment.<br>

<br>2. Raises `Exception(f"{name} expects {N} arguments!")` on arity mismatch.<br>

<br>3. Raises `Exception("OracleManager Error: Oracle '...' is missing a 'returns' clause.")` if no return clause is found. |
| """ |  |  |  |

with open("toolOracles_documentation.md", "w", encoding="utf-8") as f:
f.write(markdown_content)

print("FILE_GENERATED: toolOracles_documentation.md")

```

```text?code_stdout&code_event_index=1
FILE_GENERATED: toolOracles_documentation.md


```

I have generated and saved the standalone Markdown documentation file for `core/toolOracles.py` titled **`toolOracles_documentation.md`**. Below is the complete, unabridged technical documentation.

# TOOL Oracle Contract Manager & AST Substitution Engine (`toolOracles.py`) Documentation

**Module:** `core/toolOracles.py`

**Language:** Python 3

**Role:** Implements `ASTSubstitutor` and `OracleManager`, providing formal parameter grounding, variable capture prevention, self-recursion detection, and assume/guarantee contract extraction for TOOL axiomatic Oracle functions.

---

## 1. Architectural Overview & Oracle Axiom Mechanics

In the Typed Oracle Oriented Language (TOOL), an **Oracle** is an axiomatic specification function defined with explicit assume/guarantee contracts (`assumes` and `returns` clauses). When an imperative statement or expression invokes an oracle via `FuncCall`, the verification pipeline must mathematically connect the oracle's formal definition to the specific concrete arguments passed at the call site.

```
       [Oracle Formal Definition: oracle f(arg_1, ...) -> res]
                         │
                         │ (Formal Parameters -> Concrete Arguments)
                         │ (retName -> Call-Site FuncCall)
                         ▼
        [OracleManager.extract_contract(func_call)]
                         │
                         ▼
        [ASTSubstitutor.substitute(returns_expr / assumes_expr)]
                         │
                         ▼
 [Grounded Contract Tuple: (grounded_assumes, grounded_returns)]

```

### Key Responsibilities:

1. **Contract Grounding (`extract_contract`):** Maps formal parameter names to concrete call-site arguments and replaces occurrences of the oracle's return variable (`retName`) with the actual `FuncCall` AST node.


2. **Variable Capture Protection (`ASTSubstitutor`):** Recursively traverses contract formulas to apply substitutions while safely shadowing first-order quantifier bound variables (`forall`/`exists`), preventing accidental variable capture.


3. **Recursion Detection (`is_recursive`):** Analyzes oracle bodies to determine whether an oracle is self-recursive, signaling to downstream Z3 translation whether to compile the function using `z3.RecFunction` or inline expansion.



---

## 2. AST Substitution Engine (`ASTSubstitutor`)

```python
class ASTSubstitutor:
    def __init__(self, substitution_map: Dict[str, Expr]):
        self.sub_map = substitution_map

```

The `ASTSubstitutor` class performs deep-copy transformations on AST expressions (`Expr`), replacing variable references (`VarRef`) whose identifiers match keys in `self.sub_map` with their corresponding mapped AST expressions.

### Quantifier Shadowing & Capture Prevention

When substituting variables inside first-order logic quantifiers (`Quantifier`), the substitutor enforces lexical scoping rules: if a quantifier binds a variable (`node.bound_var`) that has the same name as an entry in `self.sub_map`, the mapping is temporarily removed (shadowed) before recursing into `node.formula`, and restored immediately after.

```python
# Quantifier Shadowing Logic
shadowed_val = None
if node.bound_var in self.sub_map:
    shadowed_val = self.sub_map.pop(node.bound_var)

new_formula = self.substitute(node.formula)

if shadowed_val is not None:
    self.sub_map[node.bound_var] = shadowed_val

```

* **Why this is critical:** Without shadowing, if an oracle formal parameter is named `i`, and an inner `forall i: int . footprint[i] == 0` quantifier also uses `i`, a naive substitution would replace the quantified bound variable `i` with the caller's concrete argument, destroying the mathematical validity of the formula.

### Recursive AST Substitution Rules Table

| AST Expression Node | Transformation & Substitution Logic |
| --- | --- |
| `VarRef` | Checks if `node.name in self.sub_map`. If present, returns `self.sub_map[node.name]`; otherwise returns `node` unchanged.

 |
| `Literal` | Returns `node` unchanged (literals contain no variable references).

 |
| `BinaryExpr` | Recursively invokes `substitute` on `node.left` and `node.right`, returning a new `BinaryExpr(left, op, right)`.

 |
| `UnaryExpr` | Recursively invokes `substitute` on `node.operand`, returning a new `UnaryExpr(op, operand)`.

 |
| `TernaryExpr` | Recursively invokes `substitute` on `node.condition`, `node.true_expr`, and `node.false_expr`.

 |
| `FuncCall` | Recursively invokes `substitute` across every argument in `node.args`, returning a new `FuncCall(name, args)`.

 |
| `SeqAccess` | Recursively invokes `substitute` on both `node.seq_obj` and `node.index`.

 |
| `FieldAccess` | Recursively invokes `substitute` on `node.obj` while preserving `node.field`.

 |
| `Quantifier` | Applies temporary `self.sub_map` shadowing for `node.bound_var`, recursively substitutes inside `node.formula`, restores the map, and returns a new `Quantifier`.

 |

---

## 3. Oracle Contract Management (`OracleManager`)

```python
class OracleManager:
    def __init__(self, env: TypeEnvironment) -> None:
        self.env = env

```

The `OracleManager` interfaces directly with `TypeEnvironment` to inspect registered `FunctionDef` oracle signatures and extract call-site-grounded assume/guarantee contracts.

---

### Recursion Detection (`is_recursive`)

```python
def is_recursive(self, oracle_def: FunctionDef) -> bool:

```

* **Purpose:** Inspects an oracle definition's contract clauses (`Assume` and `Returns`) to detect whether the oracle invokes itself recursively.


* **Algorithm:** Implements a nested recursive helper function, `check_node(node: ASTNode) -> bool`, that walks every expression tree inside `oracle_def.clauses`:


* Returns `True` if it encounters a `FuncCall` where `node.name == oracle_def.name`.


* Recursively checks child expressions of `FuncCall`, `BinaryExpr`, `UnaryExpr`, `TernaryExpr`, `Quantifier`, `FieldAccess`, and `SeqAccess`.




* **Downstream Integration:** In `toolSSA.py` and `toolZ3.py`, if `is_recursive()` returns `False`, non-recursive oracle calls can be safely macro-expanded or inlined at call sites without requiring Z3 recursive function axioms.



---

### Contract Extraction & Grounding (`extract_contract`)

```python
def extract_contract(self, func_call: FuncCall) -> tuple[Optional[Expr], Expr]:

```

The `extract_contract` method is the core operational bridge of `OracleManager`. Given a concrete `FuncCall` AST node representing an oracle invocation, it retrieves the oracle's formal contract and substitutes formal symbols with concrete call-site expressions.

#### Step-by-Step Contract Grounding Workflow:

```
[1. Lookup Oracle Definition in self.env.oracles]
                      │
                      ▼
[2. Validate Argument Count: len(args) == len(formal_args)]
                      │
                      ▼
[3. Build Substitution Map (sub_map)]
  ├── formal_arg_1.name  ──► func_call.args[0]
  ├── formal_arg_n.name  ──► func_call.args[n-1]
  └── oracle_def.retName ──► func_call (The Call-Site AST Node itself)
                      │
                      ▼
[4. Extract Assume & Returns Contract Clauses]
                      │
                      ▼
[5. Run ASTSubstitutor.substitute() on Both Clauses]
                      │
                      ▼
[Return Tuple: (grounded_assumes, grounded_returns)]

```

1. **Oracle Definition Lookup:** Retrieves `oracle_def = self.env.oracles[func_call.name]`. Raises an exception if the oracle is undefined.


2. **Arity Validation:** Enforces that `len(func_call.args) == len(oracle_def.args)`. Raises an exception if argument counts mismatch.


3. **Parameter Mapping:** Iterates over formal parameters (`oracle_def.args`), mapping each formal parameter name to the concrete call-site AST expression:


```python
sub_map[formal_arg.name] = func_call.args[i]

```


4. **Return Value Binding:** Maps the oracle's declared return variable (`oracle_def.retName`) directly to the `func_call` AST node:


```python
sub_map[oracle_def.retName] = func_call

```


* *Example:* If an oracle is defined as `oracle is_acyclic(seq: seq[int]) -> res: bool { returns res == ...; }`, calling `is_acyclic(footprint_1)` maps formal parameter `"seq"` to `VarRef("footprint_1")` and formal return variable `"res"` to `FuncCall("is_acyclic", [VarRef("footprint_1")])`.


5. **Clause Unpacking:** Scans `oracle_def.clauses` to separate the `Assume` formula (`assumes_expr`) and `Returns` formula (`returns_expr`).


6. **Mandatory Return Check:** Enforces that `returns_expr` is not `None`. Raises an exception if an oracle lacks a `returns` clause.


7. **AST Substitution:** Instantiates `ASTSubstitutor(sub_map)` and executes `.substitute()` on both formulas, producing `(grounded_assumes, grounded_returns)`.



---

## 4. Complete Method & Error Reference Table

| Method / Class | Input Parameters | Return Type | Exception / Error Condition |
| --- | --- | --- | --- |
| `ASTSubstitutor.substitute` | `node: Expr` | `Expr` | None

 |
| `OracleManager.is_recursive` | `oracle_def: FunctionDef` | `bool` | None

 |
| `OracleManager.extract_contract` | `func_call: FuncCall` | `tuple[Optional[Expr], Expr]` | 1. Raises `Exception(f"Oralce {name} is not defined!")` if missing from environment.

<br>

<br>2. Raises `Exception(f"{name} expects {N} arguments!")` on arity mismatch.

<br>

<br>3. Raises `Exception("OracleManager Error: Oracle '...' is missing a 'returns' clause.")` if no return clause is found.
