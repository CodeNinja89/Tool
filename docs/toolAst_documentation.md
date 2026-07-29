# TOOL Abstract Syntax Tree (`toolAst.py`) Documentation

**Module:** `core/toolAst.py`  
**Language:** Python 3 (Typed Dataclasses)  
**Role:** Defines the complete Abstract Syntax Tree (AST) and semantic data structures for the Typed Oracle Oriented Language (TOOL).

---

## 1. Architectural Overview

The `toolAst.py` module establishes the formal semantic representation of any TOOL verification program. Every structural component—from top-level program sections and user-defined structs to temporal traces, first-order quantifiers, and imperative loops—is modeled as a strongly typed `@dataclass` inheriting from `ASTNode`.

This AST serves as the primary data exchange format across the entire verification pipeline:
1. **Parser (`toolParser.py`)**: Transforms concrete syntax trees from Lark into `ASTNode` instances.
2. **Type Checker (`toolTypeChecker.py`)**: Traverses `ASTNode` trees to enforce type safety, linear resource typing (`linear struct`), and operator compatibility.
3. **SSA Transformer (`toolSSA.py`)**: Rewrites imperative AST statements (`AssignStmt`, `WhileStmt`) into purely functional Single Static Assignment equations (`StructUpdate`, `SeqUpdate`, `LoopTransition`).
4. **Z3 Translator (`toolZ3.py`)**: Translates AST expressions directly into Z3 SMT solver terms, user-defined algebraic datatypes, and recursive function definitions.

---

## 2. Complete Class Hierarchy

```
ASTNode
 ├── Program
 ├── Assume
 ├── Returns
 ├── VarDecl
 ├── InvisibleDecl
 ├── ConstDecl
 ├── StructDef
 ├── FunctionDef
 ├── EnvDef
 ├── TraceDef
 ├── Expr
 │    ├── BinaryExpr
 │    ├── TernaryExpr
 │    ├── UnaryExpr
 │    ├── Quantifier
 │    ├── VarRef
 │    ├── Literal
 │    ├── FuncCall
 │    ├── FieldAccess
 │    ├── SeqAccess
 │    ├── StructUpdate
 │    ├── SeqUpdate
 │    └── LoopTransition
 ├── CallSiteCheck
 └── Stmt
      ├── AssignStmt
      ├── AssertStmt
      ├── FactStmt
      ├── BlockStmt
      ├── IfStmt
      └── WhileStmt
```

---

## 3. Top-Level Program & Base Nodes

### `ASTNode`
```python
@dataclass
class ASTNode:
    pass
```
The root superclass for all AST nodes in the TOOL ecosystem. Provides a common polymorphic type for AST traversal and visitor patterns.

---

### `Program`
```python
@dataclass
class Program(ASTNode):
    declarations: List[ASTNode]
    preconditions: List[ASTNode]
    postconditions: List[ASTNode]
    specProgram: List[ASTNode]
```
Represents a fully parsed TOOL specification file, structured into four distinct logical sections:

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `declarations` | `List[ASTNode]` | Top-level declarations including variables, constants, structs, environment functions, traces, and oracles. |
| `preconditions` | `List[ASTNode]` | Boolean formulas (`Expr`) representing initial assumptions about the starting state. |
| `postconditions` | `List[ASTNode]` | Boolean formulas (`Expr`) that must be mathematically proven valid after executing `specProgram`. |
| `specProgram` | `List[ASTNode]` | Sequential imperative statements (`Stmt`) modeling state transitions and intermediate assertions. |

---

## 4. Declaration Nodes

### `VarDecl`
```python
@dataclass
class VarDecl(ASTNode):
    name: str
    typeName: str
    is_refer: bool = False
```
Defines a variable declaration or function parameter.
* **`name`**: Identifier name.
* **`typeName`**: Type signature string (e.g., `"int"`, `"bool"`, `"seq[int]"`, or a user-defined struct name).
* **`is_refer`**: When `True`, indicates a reference parameter (`refer`). This signals to the linear type checker that passing a linear struct to this function does not consume or invalidate the caller's resource.

---

### `InvisibleDecl`
```python
@dataclass
class InvisibleDecl(ASTNode):
    name: str
    typeName: str
```
Defines a ghost/invisible variable (`invisible x: int;`) used purely for auxiliary specification logic and invariant framing without altering concrete program execution.

---

### `ConstDecl`
```python
@dataclass
class ConstDecl(ASTNode):
    name: str
    typeName: str
```
Defines an immutable top-level constant. Any assignment targeting a `ConstDecl` variable is rejected by the type checker.

---

### `StructDef`
```python
@dataclass
class StructDef(ASTNode):
    name: str
    fields: Dict[str, str]
    is_linear: bool = False
```
Defines a user-defined Algebraic Data Type (ADT).
* **`name`**: Struct identifier.
* **`fields`**: Ordered dictionary mapping field names to their type strings.
* **`is_linear`**: When set to `True` (`linear struct`), enforces linear typing rules: instances must be consumed exactly once, preventing memory leaks and use-after-free errors.

---

### `FunctionDef`
```python
@dataclass
class FunctionDef(ASTNode):
    name: str
    args: List[VarDecl]
    retName: str
    retType: str
    clauses: List[ASTNode]
```
Represents an **Oracle**—an axiomatic function definition with assume/guarantee contracts.
* **`name`**: Oracle identifier.
* **`args`**: List of formal parameters (`VarDecl`).
* **`retName`**: Variable name bound to the return value inside contract clauses.
* **`retType`**: Type string of the return value.
* **`clauses`**: List of contract statements (`Assume` and `Returns` nodes) defining the oracle's mathematical behavior.

---

### `EnvDef`
```python
@dataclass
class EnvDef(ASTNode):
    name: str
    args: List[VarDecl]
    retName: str
    retType: str
```
Represents an external environment function (`env`). Unlike oracles, environment functions model unconstrained external behaviors and are compiled into uninterpreted Z3 functions.

---

### `TraceDef`
```python
@dataclass
class TraceDef(ASTNode):
    name: str
    time_var: str
    ret_name: str
    ret_type: str
    init_expr: Expr
    step_expr: Expr
```
Defines a temporal trace function over discrete timesteps (`timestep`).
* **`time_var`**: Parameter identifier representing the timestep index.
* **`init_expr`**: Mathematical formula defining the state at timestep `0`.
* **`step_expr`**: Inductive transition formula defining the state at arbitrary positive timesteps (`t > 0`).

---

## 5. Mathematical & Logical Expressions (`Expr`)

All evaluable formulas and terms inherit from `Expr`.

### `BinaryExpr`
```python
@dataclass
class BinaryExpr(Expr):
    left: Expr
    op: str
    right: Expr
```
Represents binary operators across logical (`&&`, `||`), relational (`==`, `!=`, `<`, `<=`, `>`, `>=`), arithmetic (`+`, `-`, `*`, `/`, `%`), and bitwise (`&`, `|`, `^`, `<<`, `>>`) operations.

---

### `TernaryExpr`
```python
@dataclass
class TernaryExpr(Expr):
    condition: Expr
    true_expr: Expr
    false_expr: Expr
```
Represents conditional selection (`condition ? true_expr : false_expr`). Compiled to `z3.If` in the SMT backend.

---

### `UnaryExpr`
```python
@dataclass
class UnaryExpr(Expr):
    op: str
    operand: Expr
```
Represents unary operators: logical negation (`!`), arithmetic negation (`-`), and bitwise complement (`~`).

---

### `Quantifier`
```python
@dataclass
class Quantifier(Expr):
    quant_type: str
    bound_var: str
    var_type: str
    formula: Expr
```
Represents first-order logic quantifiers (`forall` and `exists`).
* **`quant_type`**: Either `"forall"` or `"exists"`.
* **`bound_var`**: Variable name bound within the quantifier scope.
* **`var_type`**: Type of the bound variable.
* **`formula`**: Inner expression quantified over.

---

### `VarRef`
```python
@dataclass
class VarRef(Expr):
    name: str
```
A variable reference. During SSA transformation, identifiers are dynamically versioned (e.g., `x` -> `x_0`, `x_1`).

---

### `Literal`
```python
@dataclass
class Literal(Expr):
    value: str
```
Represents constant literal strings: integers (`"42"`), booleans (`"true"`, `"false"`), and `"null"` pointers.

---

### `FuncCall`
```python
@dataclass
class FuncCall(Expr):
    name: str
    args: List[Expr]
    
```
Represents a function invocation targeting an Oracle, Environment function, Trace function, or Z3 constructor (`mk_Struct`).

---

### `FieldAccess`
```python
@dataclass
class FieldAccess(Expr):
    obj: Expr
    field: str
```
Represents field navigation (`obj.field`) on struct types or sequence length retrieval (`seq.length`).

---

### `SeqAccess`
```python
@dataclass
class SeqAccess(Expr):
    seq_obj: Expr
    index: Expr
```
Represents sequence indexing (`seq_obj[index]`). Compiled to SMT array `Select` operations.

---

## 6. Functional SSA Mutations & Inductive Loop Transitions

Because SMT solvers require purely functional equations without side effects, imperative modifications are translated into the following expression nodes:

### `StructUpdate`
```python
@dataclass
class StructUpdate(Expr):
    obj: Expr
    field: str
    new_value: Expr
```
Represents a functional Single Static Assignment (SSA) update of a struct field, generating a new struct instance with the specified field updated while preserving all other fields.

---

### `SeqUpdate`
```python
@dataclass
class SeqUpdate(Expr):
    seq_obj: Expr
    index: Expr
    new_value: Expr
```
Represents a functional SSA update of a sequence element at `index`. Compiled to an SMT array `Store` operation.

---

### `LoopTransition`
```python
@dataclass
class LoopTransition(Expr):
    pre_loop_scope: Dict[str, int]
    read_scope: Dict[str, int]
    write_scope: Dict[str, int]
    inv_pre: Expr
    inv_read: Expr
    inv_write: Expr
    cond_read: Expr
    body_formulas: List[Expr]
```
A specialized AST node generated by the SSA Transformer to verify `while` loops using mathematical induction:
* **`pre_loop_scope`**: Variable versions immediately prior to loop entry.
* **`read_scope`**: Havoced variable versions at the start of an arbitrary $i$-th iteration (Inductive Hypothesis).
* **`write_scope`**: Variable versions after executing the loop body (Inductive Proof).
* **`inv_pre`**: Loop invariant evaluated before the loop (Base Case).
* **`inv_read`**: Invariant assumed true at start of iteration ($P(k)$).
* **`inv_write`**: Invariant proven true at end of iteration ($P(k+1)$).
* **`cond_read`**: Loop continuation condition evaluated at `read_scope`.
* **`body_formulas`**: Functional state transition formulas representing the loop body.

---

## 7. Contract Clauses & Verification Statements (`Stmt`)

### `CallSiteCheck`
```python
@dataclass
class CallSiteCheck:
    formula: Expr
```
Wraps an oracle's grounded `assumes` contract formula at a call site, enforcing that the caller satisfies all preconditions before invoking the oracle.

---

### `Assume` & `Returns`
```python
@dataclass
class Assume(ASTNode):
    formula: Expr

@dataclass
class Returns(ASTNode):
    formula: Expr
```
Contract clauses embedded inside `FunctionDef` clauses:
* **`Assume`**: Precondition assumed to hold upon oracle invocation.
* **`Returns`**: Postcondition defining the return value's mathematical relation to the inputs.

---

### Imperative Specification Statements (`Stmt`)

```python
@dataclass
class Stmt(ASTNode):
    pass
```
Base class for all imperative statements within `specProgram` or block bodies.

#### `AssignStmt`
```python
@dataclass
class AssignStmt(Stmt):
    lvalue: VarRef
    expr: Expr
```
An imperative assignment (`lvalue := expr;`). Converted by the SSA engine into an equality constraint (`x_1 == expr`).

#### `AssertStmt`
```python
@dataclass
class AssertStmt(Stmt):
    formula: Expr
```
An explicit verification proof obligation (`assert formula;`). The verifier pushes the negated formula to Z3 to check for satisfiability (potential violations).

#### `FactStmt`
```python
@dataclass
class FactStmt(Stmt):
    formula: Expr
```
An axiomatic assumption (`fact formula;`). Added directly to the SMT solver's baseline assertions without requiring proof.

#### `BlockStmt`
```python
@dataclass
class BlockStmt(Stmt):
    statements: List[Stmt]
```
An ordered container of statements enclosed in curly braces (`{ ... }`).

#### `IfStmt`
```python
@dataclass
class IfStmt(Stmt):
    condition: Expr
    then_block: BlockStmt
    else_block: Optional[BlockStmt]
```
An imperative branching statement. SSA transformation generates functional $\Phi$ (phi) nodes to merge divergent variable timelines from the `then_block` and `else_block`.

#### `WhileStmt`
```python
@dataclass
class WhileStmt(Stmt):
    condition: Expr
    invariant: Optional[Expr]
    body: BlockStmt
```
An imperative loop statement. Requires an optional inductive `invariant` expression to enable inductive loop verification via `LoopTransition`.
