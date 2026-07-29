# TOOL Parser & AST Builder (`toolParser.py`) Documentation

**Module:** `core/toolParser.py`  
**Language:** Python 3  
**Role:** Serves as the syntactic-to-semantic bridge for the Typed Oracle Oriented Language (TOOL), converting Lark concrete parse trees into strongly typed AST dataclass instances.

---

## 1. Architectural Overview & Lark Integration

In Lark's LALR parser workflow, when a grammar rule from `toolGrammar.lark` is matched, it generates a parse tree node. The `Z3Transformer` class, which inherits from Lark's `Transformer`, processes these nodes bottom-up. Each grammar rule corresponds to a transformer method of the same name, receiving a Python list named `items` containing the transformed child nodes or matched lexer tokens.


```

Raw Lark Parse Tree (Concrete Syntax)
│
▼
Z3Transformer (toolParser.py)
│
▼
Typed AST Nodes (toolAst.py)

```

### Key Parsing Behaviors:
* **Token Conversion:** Leaf rules (identifiers, literals) are explicitly cast to Python strings (`str(items[0])`) before being wrapped in AST nodes.
* **Optional Tokens:** Grammar rules using optional constructs (e.g., `[LINEAR]`, `[REFER]`, or `[arg_list]`) pass `None` within `items` when omitted in the source file, requiring explicit `None` checks in the transformer methods.

---

## 2. Top-Level Program & Section Transformers

These methods assemble the top-level `Program` AST node by organizing the four main sections of a TOOL specification file.

### `start(self, items)`
* **Input Items:** `items[0]` contains the evaluated result of `structured_program`.
* **Behavior:** Serves as the root entry point of the transformer, returning `items[0]` directly.

### `structured_program(self, items)`
* **Input Items:** A 4-element list: `[declarations_section, preconditions_section, postconditions_section, program_section]`.
* **Behavior:** Instantiates and returns the top-level `Program` AST node:
  ```python
  return Program(
      declarations=items[0],
      preconditions=items[1],
      postconditions=items[2],
      specProgram=items[3]
  )

```

### Section Handlers

* **Methods:**
* `declarations_section(self, items)`
* `preconditions_section(self, items)`
* `postconditions_section(self, items)`
* `program_section(self, items)`


* **Behavior:** Each grammar section matches a sequence of statements or formulas. These methods act as pass-through handlers, returning `items` as a Python list of transformed AST nodes.

---

## 3. Declarations & Type Signature Transformers

### `var_decl(self, items)`

* **Input Items:** `items[0]` is the variable identifier (`NAME`), and `items[1]` is the evaluated type string.
* **Behavior:** Returns `VarDecl(name=str(items[0]), typeName=str(items[1]), is_refer=False)`. Top-level variable declarations are never passed by reference.

### `const_decl(self, items)`

* **Input Items:** `items[0]` is the constant identifier, and `items[1]` is the type string.
* **Behavior:** Returns `ConstDecl(name=str(items[0]), typeName=str(items[1]))`.

### `struct_def(self, items)`

* **Input Items:**
* `items[0]`: Optional `[LINEAR]` token (`None` if omitted).
* `items[1]`: Struct name identifier.
* `items[2:]`: Alternating sequence of field names and field type strings (`field_name_1, field_type_1, ...`).


* **Behavior:** Evaluates boolean linearity (`is_linear = items[0] is not None`), iterates through fields from index 2 in steps of 2 to build a dictionary of `fields`, and returns `StructDef(struct_name, fields, is_linear)`.

### `invisible_decl(self, items)`

* **Input Items:** `items[0]` is the matched `INVISIBLE` keyword token, `items[1]` is the variable name, and `items[2]` is the type string.
* **Behavior:** Extracts name from index 1 and type from index 2, returning `InvisibleDecl(name=str(items[1]), typeName=str(items[2]))`.

### Type System Transformers

* **`base_type(self, items)`**: Returns the base type keyword (`"int"`, `"bool"`, or `"timestep"`) as a string.
* **`user_type(self, items)`**: Returns user-defined struct identifier strings.
* **`seq_type(self, items)`**: Wraps the inner type string in sequence notation, returning `f"seq[{items[0]}]"`.

---

## 4. Oracles, Environments & Trace Transformers

### `function_def(self, items)`

* **Grammar Rule:** `"oracle" NAME "(" [arg_list] ")" "->" NAME ":" type "{" function_body "}"`
* **Input Items:** `[name, arg_list_opt, ret_name, ret_type, body]`.
* **Behavior:** Checks if `items[1]` is `None` (no arguments provided) and defaults to an empty list `[]`. Returns `FunctionDef(name, args, retName, retType, clauses)`.

### `env_def(self, items)`

* **Grammar Rule:** `"env" NAME "(" [arg_list] ")" "->" NAME ":" type ";"`
* **Input Items:** `[name, arg_list_opt, ret_name, ret_type]`.
* **Behavior:** Returns `EnvDef(name, args, retName, retType)`.

### `trace_def(self, items)`

* **Grammar Rule:** `"trace" NAME "(" NAME ":" "timestep" ")" "->" NAME ":" type "{" trace_body "}"`
* **Input Items:** `items[0]` is the trace name, `items[1]` is the timestep variable identifier, `items[2]` is the return variable name, `items[3]` is the return type, and `items[4]` is a tuple `(init_expr, step_expr)` produced by `trace_body`.
* **Behavior:** Unpacks the tuple at `items[4]` and returns `TraceDef(name, time_var, ret_name, ret_type, init_expr, step_expr)`.

### `trace_body(self, items)`

* **Input Items:** `items[0]` is the initial formula (`init : formula;`) and `items[1]` is the step formula (`step : formula;`).
* **Behavior:** Returns a 2-element tuple `(items[0], items[1])` to be consumed by `trace_def`.

### Parameters & Function Clauses

* **`arg_list(self, items)`**: Returns the list of transformed `VarDecl` parameter nodes.
* **`arg(self, items)`**: Checks if the optional `[REFER]` token at `items[0]` is present (`is_refer = items[0] is not None`), and returns `VarDecl(name=str(items[1]), typeName=str(items[2]), is_refer=is_refer)`.
* **`function_body(self, items)`**: Returns the list of contract clause nodes (`Assume` and `Returns`).
* **`func_assumes(self, items)`**: Wraps `items[0]` in `Assume(formula=items[0])`.
* **`func_returns(self, items)`**: Wraps `items[0]` in `Returns(formula=items[0])`.

---

## 5. Logical, Arithmetic & Relational Expression Transformers

The parser converts Lark concrete operators directly into unified AST expression structures.

### Binary & Unary Operator Mappings

| Method | Operator String | AST Node Generated | Input Items |
| --- | --- | --- | --- |
| `eq` | `'=='` | `BinaryExpr(left, '==', right)` | `items[0]`, `items[1]` |
| `neq` | `'!='` | `BinaryExpr(left, '!=', right)` | `items[0]`, `items[1]` |
| `lt` | `'<'` | `BinaryExpr(left, '<', right)` | `items[0]`, `items[1]` |
| `lte` | `'<='` | `BinaryExpr(left, '<=', right)` | `items[0]`, `items[1]` |
| `gt` | `'>'` | `BinaryExpr(left, '>', right)` | `items[0]`, `items[1]` |
| `gte` | `'>='` | `BinaryExpr(left, '>=', right)` | `items[0]`, `items[1]` |
| `add` | `'+'` | `BinaryExpr(left, '+', right)` | `items[0]`, `items[1]` |
| `sub` | `'-'` | `BinaryExpr(left, '-', right)` | `items[0]`, `items[1]` |
| `mul` | `'*'` | `BinaryExpr(left, '*', right)` | `items[0]`, `items[1]` |
| `div` | `'/'` | `BinaryExpr(left, '/', right)` | `items[0]`, `items[1]` |
| `mod` | `'%'` | `BinaryExpr(left, '%', right)` | `items[0]`, `items[1]` |
| `logic_and_op` | `'&&'` | `BinaryExpr(left, '&&', right)` | `items[0]`, `items[1]` |
| `logic_or_op` | `' |  | '` |
| `bit_or_op` | `' | '` | `BinaryExpr(left, ' |
| `bit_xor_op` | `'^'` | `BinaryExpr(left, '^', right)` | `items[0]`, `items[1]` |
| `bit_and_op` | `'&'` | `BinaryExpr(left, '&', right)` | `items[0]`, `items[1]` |
| `shl` | `'<<'` | `BinaryExpr(left, '<<', right)` | `items[0]`, `items[1]` |
| `shr` | `'>>'` | `BinaryExpr(left, '>>', right)` | `items[0]`, `items[1]` |
| `not_f` | `'!'` | `UnaryExpr('!', operand)` | `items[0]` |
| `neg` | `'-'` | `UnaryExpr('-', operand)` | `items[0]` |
| `bit_not` | `'~'` | `UnaryExpr('~', operand)` | `items[0]` |

---

### Special Formulas & Atoms

#### `ite_expr(self, items)`

* **Behavior:** Converts ternary expressions (`cond ? true_expr : false_expr`) into `TernaryExpr(condition=items[0], true_expr=items[1], false_expr=items[2])`.

#### `forall_f(self, items)` & `exists_f(self, items)`

* **Input Items:** `items[0]` is the bound variable name (`NAME`), `items[1]` is the type string, and `items[2]` is the inner quantified formula.
* **Behavior:** Returns `Quantifier(quant_type="forall"|"exists", bound_var=str(items[0]), var_type=str(items[1]), formula=items[2])`.

#### Literals & Constants

* **`number(self, items)`**: Returns `Literal(value=str(items[0]))`.
* **`true_lit(self, items)`**: Returns `Literal("true")`.
* **`false_lit(self, items)`**: Returns `Literal("false")`.
* **`null_lit(self, items)`**: Returns `Literal("null")`.

#### `lvalue(self, items)`

This method resolves variable names, chained struct field lookups, and sequence indexing.

* **Base Resolution:** Creates a base `VarRef(str(items[0]))` from the primary identifier.
* **Chain Navigation:** If `len(items) == 1`, it returns the simple `VarRef`. Otherwise, it iterates through `items[1:]`:
* If the modifier is an instance of `Expr` (e.g., `[idx]`), it wraps the current expression in `SeqAccess(seq_obj=current_expr, index=modifier)`.
* If the modifier is a string/identifier (e.g., `.val` or `.length`), it wraps the current expression in `FieldAccess(obj=current_expr, field=str(modifier))`.



#### `func_call(self, items)`

* **Input Items:** `items[0]` is the function identifier (`NAME`); `items[1]` is the optional argument list (`[expr_list]`).
* **Behavior:** Checks if arguments exist (`len(items) > 1 and items[1] is not None`) and defaults to `[]` if empty. Returns `FuncCall(name=str(items[0]), args=args)`.

#### `expr_list(self, items)`

* **Behavior:** Pass-through handler returning `items` as a Python list of expressions.

---

## 6. Imperative Specification Statement Transformers

These methods transform imperative specification statements inside `specProgram` or block bodies.

### `assign_stmt(self, items)`

* **Input Items:** `items[0]` is the target l-value (`VarRef`, `FieldAccess`, or `SeqAccess`), and `items[1]` is the evaluated expression.
* **Behavior:** Returns `AssignStmt(lvalue=items[0], expr=items[1])`.

### `assert_stmt(self, items)`

* **Input Items:** `items[0]` is the boolean formula to prove.
* **Behavior:** Returns `AssertStmt(formula=items[0])`.

### `fact_stmt(self, items)`

* **Input Items:** `items[0]` is the boolean formula assumed true.
* **Behavior:** Returns `FactStmt(formula=items[0])`.

### `block_stmt(self, items)`

* **Input Items:** A variable number of statements enclosed within braces `{ ... }`.
* **Behavior:** Returns `BlockStmt(statements=items)`.

### `if_stmt(self, items)`

* **Input Items:** `items[0]` is the condition formula, `items[1]` is the `then_block`, and `items[2]` is the optional `else_block` (if present).
* **Behavior:** Evaluates whether `len(items) > 2` to attach the `else_block` or set it to `None`, returning `IfStmt(condition, then_block, else_block)`.

### `while_stmt(self, items)`

* **Grammar Rule:** `"while" "(" formula ")" ["invariant" formula] block_stmt`
* **Input Items:** Depending on whether optional clauses are present, `items` contains between 2 and 4 elements.
* **Behavior:**
* `condition` is always at `items[0]`, and the loop `body` is always at `items[-1]`.
* If `len(items) == 3` or `len(items) == 4`, `invariant` is extracted from `items[1]`.
* Returns `WhileStmt(condition, invariant, body)`.