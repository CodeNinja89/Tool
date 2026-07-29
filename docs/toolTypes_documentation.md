# TOOL Type Environment (`toolTypes.py`) Documentation

**Module:** `core/toolTypes.py`  
**Language:** Python 3  
**Role:** Implements the `TypeEnvironment` class, which serves as the centralized symbol table and static typing context ($\Gamma$) for the Typed Oracle Oriented Language (TOOL).

---

## 1. Architectural Overview & Symbol Table Role

The `TypeEnvironment` class acts as the authoritative repository of type metadata, struct layouts, linear resource classifications, immutability rules, and callable definitions across the entire TOOL verification pipeline [cite: 7]. 

During compilation, `TypeEnvironment` is constructed once after parsing by passing the top-level `declarations` list from `Program` into `build()` [cite: 7, 10]. Once populated, this environment is queried by:
1. **Type Checker (`toolTypeChecker.py`)**: Resolves variable types, validates struct field accessors, enforces immutability on `const` variables, and identifies `linear struct` types for use-after-free and memory leak detection [cite: 6, 7].
2. **SSA Transformer (`toolSSA.py`)**: Looks up struct field layouts and sequence types when generating functional updates (`StructUpdate`, `SeqUpdate`) and checks whether invoked calls are oracles requiring contract assumptions/guarantees (`CallSiteCheck`) [cite: 5, 7].
3. **Z3 Translator (`toolZ3.py`)**: Queries struct field names and types to register Z3 algebraic datatypes (`DatatypeSortRef`) and fetches oracle/environment/trace signatures to compile Z3 `RecFunction` and uninterpreted `Function` declarations [cite: 7, 8].

---

## 2. State & Storage Architecture

When a `TypeEnvironment` instance is initialized via `__init__(self)`, it creates eight distinct data structures to track different semantic categories of the TOOL language [cite: 7]:


```

TypeEnvironment
├── variables: Dict[str, str]                 # Global/scope variable name -> Type signature
├── structs: Dict[str, Dict[str, str]]        # Struct name -> {Field name -> Type signature}
├── oracles: Dict[str, FunctionDef]           # Oracle name -> FunctionDef AST node
├── envs: Dict[str, EnvDef]                   # Env function name -> EnvDef AST node
├── traces: Dict[str, TraceDef]               # Trace function name -> TraceDef AST node
├── linear_structs: set                       # Set of struct names declared with [LINEAR]
├── invisible_vars: set                       # Set of variable names declared as INVISIBLE
└── constant_vars: set                        # Set of variable names declared as CONST

```

### Attribute Breakdown

| Attribute | Type | Description & Downstream Purpose |
| :--- | :--- | :--- |
| `variables` | `Dict[str, str]` | Maps variable identifier names to their string type representations (e.g., `"int"`, `"bool"`, `"seq[int]"`, or `"Node"`) [cite: 7]. |
| `structs` | `Dict[str, Dict[str, str]]` | Maps struct names to an inner dictionary of field layouts (e.g., `{"Node": {"value": "int", "next": "Node"}}`) [cite: 7]. |
| `oracles` | `Dict[str, FunctionDef]` | Stores parsed Oracle definitions (`FunctionDef` AST nodes) indexed by oracle name [cite: 1, 7]. |
| `envs` | `Dict[str, EnvDef]` | Stores external Environment function signatures (`EnvDef` AST nodes) indexed by name [cite: 1, 7]. |
| `traces` | `Dict[str, TraceDef]` | Stores temporal trace definitions (`TraceDef` AST nodes) indexed by trace name [cite: 1, 7]. |
| `linear_structs` | `set` | Tracks which user-defined structs were declared with the `linear` keyword [cite: 7]. Used by `TypeChecker` to initialize the linear resource delta ($\Delta$) [cite: 6, 7]. |
| `invisible_vars` | `set` | Tracks variables declared with the `invisible` keyword (ghost variables) [cite: 7]. When assigned to, the RHS expression is treated as a reference (`refer`), preventing linear resource consumption [cite: 6, 7]. |
| `constant_vars` | `set` | Tracks immutable constants declared via `const` [cite: 7]. The type checker rejects any assignment targeting a variable in this set [cite: 6, 7]. |

---

## 3. Declaration Builder (`build`)

```python
def build(self, declarations: List[ASTNode]):

```

The `build` method traverses the top-level declaration AST nodes produced by the parser and registers each symbol into its appropriate lookup tables and category sets .

### Declaration Processing Rules

1. **`VarDecl`** :


* Registers the variable name and type in `self.variables[decl.name] = decl.typeName` .




2. **`ConstDecl`** :


* Adds the identifier to `self.constant_vars.add(decl.name)` .


* Registers the variable name and type in `self.variables[decl.name] = decl.typeName` .




3. **`InvisibleDecl`** :


* Adds the identifier to `self.invisible_vars.add(decl.name)` .


* Registers the variable name and type in `self.variables[decl.name] = decl.typeName` .




4. **`StructDef`** :


* Maps field layouts in `self.structs[decl.name] = decl.fields` .


* If `decl.is_linear` is `True`, adds the struct name to `self.linear_structs.add(decl.name)` .




5. **`FunctionDef` (Oracles)** :


* Stores the complete AST node in `self.oracles[decl.name] = decl` .




6. **`EnvDef`** :


* Stores the external environment signature AST node in `self.envs[decl.name] = decl` .




7. **`TraceDef`** :


* Stores the temporal trace AST node in `self.traces[decl.name] = decl` .





---

## 4. Variable & Type Query API

These methods allow compiler passes to inspect variable types, check immutability constraints, and retrieve struct field layouts .

### `get_var_type(self, var_name: str) -> str`

* **Purpose:** Retrieves the declared type signature of a variable .


* **Behavior:** Checks if `var_name` exists in `self.variables` . If found, returns the type string .


* **Error Handling:** Raises `Exception(f"Variable {var_name} is not defined")` if the variable is not present in the environment .



### `is_constant(self, var_name: str) -> bool`

* **Purpose:** Checks whether a variable is an immutable top-level constant .


* **Behavior:** Returns `True` if `var_name in self.constant_vars`, otherwise `False` .



### `get_struct_fields(self, struct_name: str) -> Dict[str, str]`

* **Purpose:** Retrieves the field layout dictionary (`fieldName -> typeName`) for a registered struct .


* **Behavior:** Checks if `struct_name` exists in `self.structs` . If found, returns the field dictionary .


* **Error Handling:** Raises `Exception(f"Struct {struct_name} not defined")` if the struct has not been registered .



---

## 5. Function, Oracle & Trace Query API

When evaluating a function call expression (`FuncCall`), compiler stages query these methods to determine whether the call targets an oracle, an environment function, or a temporal trace .

### Oracle Queries

* **`is_oracle(self, func_name: str) -> bool`**: Returns `True` if `func_name` is present in `self.oracles` .


* **`get_oracles(self, oracle_name: str) -> FunctionDef`**: Returns the parsed `FunctionDef` AST node for `oracle_name` . Raises `Exception(f"Oracle {oracle_name} is not defined")` if missing .



### Environment Function Queries

* **`is_env(self, func_name: str) -> bool`**: Returns `True` if `func_name` is present in `self.envs` .


* **`get_envs(self, env_name: str) -> EnvDef`**: Returns the parsed `EnvDef` AST node for `env_name` . Raises `Exception(f"Env {env_name} is not defined")` if missing .



### Trace Queries

* **`is_trace(self, func_name: str) -> bool`**: Returns `True` if `func_name` is present in `self.traces` .


* **`get_trace(self, trace_name: str) -> TraceDef`**: Returns the parsed `TraceDef` AST node for `trace_name` . Raises `Exception(f"Trace {trace_name} is not defined")` if missing .



---

## 6. Complete Method Reference Table

| Method Signature | Input | Return Type | Exception Condition |
| --- | --- | --- | --- |
| `build(self, declarations)` | `List[ASTNode]` | `None` | None (silently ignores unknown AST types) 

 |
| `get_var_type(self, var_name)` | `str` | `str` | Raises `Exception` if `var_name` is not in `variables` 

 |
| `is_constant(self, var_name)` | `str` | `bool` | None 

 |
| `get_struct_fields(self, struct_name)` | `str` | `Dict[str, str]` | Raises `Exception` if `struct_name` is not in `structs` 

 |
| `is_oracle(self, func_name)` | `str` | `bool` | None 

 |
| `is_env(self, func_name)` | `str` | `bool` | None 

 |
| `is_trace(self, func_name)` | `str` | `bool` | None 

 |
| `get_oracles(self, oracle_name)` | `str` | `FunctionDef` | Raises `Exception` if `oracle_name` is not in `oracles` 

 |
| `get_envs(self, env_name)` | `str` | `EnvDef` | Raises `Exception` if `env_name` is not in `envs` 

 |
| `get_trace(self, trace_name)` | `str` | `TraceDef` | Raises `Exception` if `trace_name` is not in `traces` 

 |
| """ |  |  |  |

with open("toolTypes_documentation.md", "w", encoding="utf-8") as f:
f.write(markdown_content)

print("FILE_GENERATED: toolTypes_documentation.md")

```

```text?code_stdout&code_event_index=1
FILE_GENERATED: toolTypes_documentation.md


```

I have generated the detailed Markdown file for `core/toolTypes.py` titled **`toolTypes_documentation.md`**.

# TOOL Type Environment (`toolTypes.py`) Documentation

**Module:** `core/toolTypes.py`

**Language:** Python 3

**Role:** Implements the `TypeEnvironment` class, which serves as the centralized symbol table and static typing context ($\Gamma$) for the Typed Oracle Oriented Language (TOOL).

---

## 1. Architectural Overview & Symbol Table Role

The `TypeEnvironment` class acts as the authoritative repository of type metadata, struct layouts, linear resource classifications, immutability rules, and callable definitions across the entire TOOL verification pipeline.

During compilation, `TypeEnvironment` is constructed once after parsing by passing the top-level `declarations` list from `Program` into `build()`. Once populated, this environment is queried by:

1. **Type Checker (`toolTypeChecker.py`)**: Resolves variable types, validates struct field accessors, enforces immutability on `const` variables, and identifies `linear struct` types for use-after-free and memory leak detection.


2. **SSA Transformer (`toolSSA.py`)**: Looks up struct field layouts and sequence types when generating functional updates (`StructUpdate`, `SeqUpdate`) and checks whether invoked calls are oracles requiring contract assumptions/guarantees (`CallSiteCheck`).


3. **Z3 Translator (`toolZ3.py`)**: Queries struct field names and types to register Z3 algebraic datatypes (`DatatypeSortRef`) and fetches oracle/environment/trace signatures to compile Z3 `RecFunction` and uninterpreted `Function` declarations.



---

## 2. State & Storage Architecture

When a `TypeEnvironment` instance is initialized via `__init__(self)`, it creates eight distinct data structures to track different semantic categories of the TOOL language:

```
TypeEnvironment
 ├── variables: Dict[str, str]                 # Global/scope variable name -> Type signature
 ├── structs: Dict[str, Dict[str, str]]        # Struct name -> {Field name -> Type signature}
 ├── oracles: Dict[str, FunctionDef]           # Oracle name -> FunctionDef AST node
 ├── envs: Dict[str, EnvDef]                   # Env function name -> EnvDef AST node
 ├── traces: Dict[str, TraceDef]               # Trace function name -> TraceDef AST node
 ├── linear_structs: set                       # Set of struct names declared with [LINEAR]
 ├── invisible_vars: set                       # Set of variable names declared as INVISIBLE
 └── constant_vars: set                        # Set of variable names declared as CONST

```

### Attribute Breakdown

| Attribute | Type | Description & Downstream Purpose |
| --- | --- | --- |
| `variables` | `Dict[str, str]` | Maps variable identifier names to their string type representations (e.g., `"int"`, `"bool"`, `"seq[int]"`, or `"Node"`).

 |
| `structs` | `Dict[str, Dict[str, str]]` | Maps struct names to an inner dictionary of field layouts (e.g., `{"Node": {"value": "int", "next": "Node"}}`).

 |
| `oracles` | `Dict[str, FunctionDef]` | Stores parsed Oracle definitions (`FunctionDef` AST nodes) indexed by oracle name.

 |
| `envs` | `Dict[str, EnvDef]` | Stores external Environment function signatures (`EnvDef` AST nodes) indexed by name.

 |
| `traces` | `Dict[str, TraceDef]` | Stores temporal trace definitions (`TraceDef` AST nodes) indexed by trace name.

 |
| `linear_structs` | `set` | Tracks which user-defined structs were declared with the `linear` keyword. Used by `TypeChecker` to initialize the linear resource delta ($\Delta$).

 |
| `invisible_vars` | `set` | Tracks variables declared with the `invisible` keyword (ghost variables). When assigned to, the RHS expression is treated as a reference (`refer`), preventing linear resource consumption.

 |
| `constant_vars` | `set` | Tracks immutable constants declared via `const`. The type checker rejects any assignment targeting a variable in this set.

 |

---

## 3. Declaration Builder (`build`)

```python
def build(self, declarations: List[ASTNode]):

```

The `build` method traverses the top-level declaration AST nodes produced by the parser and registers each symbol into its appropriate lookup tables and category sets.

### Declaration Processing Rules

1. **`VarDecl`**:


* Registers the variable name and type in `self.variables[decl.name] = decl.typeName`.




2. **`ConstDecl`**:


* Adds the identifier to `self.constant_vars.add(decl.name)`.


* Registers the variable name and type in `self.variables[decl.name] = decl.typeName`.




3. **`InvisibleDecl`**:


* Adds the identifier to `self.invisible_vars.add(decl.name)`.


* Registers the variable name and type in `self.variables[decl.name] = decl.typeName`.




4. **`StructDef`**:


* Maps field layouts in `self.structs[decl.name] = decl.fields`.


* If `decl.is_linear` is `True`, adds the struct name to `self.linear_structs.add(decl.name)`.




5. **`FunctionDef` (Oracles)**:


* Stores the complete AST node in `self.oracles[decl.name] = decl`.




6. **`EnvDef`**:


* Stores the external environment signature AST node in `self.envs[decl.name] = decl`.




7. **`TraceDef`**:


* Stores the temporal trace AST node in `self.traces[decl.name] = decl`.





---

## 4. Variable & Type Query API

These methods allow compiler passes to inspect variable types, check immutability constraints, and retrieve struct field layouts.

### `get_var_type(self, var_name: str) -> str`

* **Purpose:** Retrieves the declared type signature of a variable.


* **Behavior:** Checks if `var_name` exists in `self.variables`. If found, returns the type string.


* **Error Handling:** Raises `Exception(f"Variable {var_name} is not defined")` if the variable is not present in the environment.



### `is_constant(self, var_name: str) -> bool`

* **Purpose:** Checks whether a variable is an immutable top-level constant.


* **Behavior:** Returns `True` if `var_name in self.constant_vars`, otherwise `False`.



### `get_struct_fields(self, struct_name: str) -> Dict[str, str]`

* **Purpose:** Retrieves the field layout dictionary (`fieldName -> typeName`) for a registered struct.


* **Behavior:** Checks if `struct_name` exists in `self.structs`. If found, returns the field dictionary.


* **Error Handling:** Raises `Exception(f"Struct {struct_name} not defined")` if the struct has not been registered.



---

## 5. Function, Oracle & Trace Query API

When evaluating a function call expression (`FuncCall`), compiler stages query these methods to determine whether the call targets an oracle, an environment function, or a temporal trace.

### Oracle Queries

* **`is_oracle(self, func_name: str) -> bool`**: Returns `True` if `func_name` is present in `self.oracles`.


* **`get_oracles(self, oracle_name: str) -> FunctionDef`**: Returns the parsed `FunctionDef` AST node for `oracle_name`. Raises `Exception(f"Oracle {oracle_name} is not defined")` if missing.



### Environment Function Queries

* **`is_env(self, func_name: str) -> bool`**: Returns `True` if `func_name` is present in `self.envs`.


* **`get_envs(self, env_name: str) -> EnvDef`**: Returns the parsed `EnvDef` AST node for `env_name`. Raises `Exception(f"Env {env_name} is not defined")` if missing.



### Trace Queries

* **`is_trace(self, func_name: str) -> bool`**: Returns `True` if `func_name` is present in `self.traces`.


* **`get_trace(self, trace_name: str) -> TraceDef`**: Returns the parsed `TraceDef` AST node for `trace_name`. Raises `Exception(f"Trace {trace_name} is not defined")` if missing.



---

## 6. Complete Method Reference Table

| Method Signature | Input | Return Type | Exception Condition |
| --- | --- | --- | --- |
| `build(self, declarations)` | `List[ASTNode]` | `None` | None (silently ignores unknown AST types)

 |
| `get_var_type(self, var_name)` | `str` | `str` | Raises `Exception` if `var_name` is not in `variables`<br> |
| `is_constant(self, var_name)` | `str` | `bool` | None

 |
| `get_struct_fields(self, struct_name)` | `str` | `Dict[str, str]` | Raises `Exception` if `struct_name` is not in `structs`<br> |
| `is_oracle(self, func_name)` | `str` | `bool` | None

 |
| `is_env(self, func_name)` | `str` | `bool` | None

 |
| `is_trace(self, func_name)` | `str` | `bool` | None

 |
| `get_oracles(self, oracle_name)` | `str` | `FunctionDef` | Raises `Exception` if `oracle_name` is not in `oracles`<br> |
| `get_envs(self, env_name)` | `str` | `EnvDef` | Raises `Exception` if `env_name` is not in `envs`<br> |
| `get_trace(self, trace_name)` | `str` | `TraceDef` | Raises `Exception` if `trace_name` is not in `traces`<br> |