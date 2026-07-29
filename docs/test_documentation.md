# TOOL Verification Test Harness (`test.py`) Documentation

**Module:** `test.py`  
**Language:** Python 3  
**Role:** Serves as the top-level command-line driver and verification test harness for the Typed Oracle Oriented Language (TOOL), orchestrating lexical parsing, symbol table construction, static linear type checking, Single Static Assignment (SSA) transformation, Z3 SMT translation, and multi-stage theorem proving.

---

## 1. Architectural Overview & Verification Pipeline

The `test.py` script ties together every component of the `core/` package into a unified, end-to-end formal verification pipeline. Rather than asserting the entire program into Z3 as a single monolithic block, the harness uses a **multi-stage incremental proof architecture** that verifies proof obligations (call-site contracts, assertions, loop invariants, and postconditions) against an evolving mathematical timeline (`timeline_facts`).

```
                    [Source File: *.tool] + [toolGrammar.lark]
                                         │
                                         ▼
                             [Lark LALR(1) Parser]
                                         │
                                         ▼
                      [Z3Transformer (toolParser.py)]
                                         │
                                         ▼
                  [TypeEnvironment.build() (toolTypes.py)]
                                         │
                                         ▼
                 [TypeChecker.check_program() (toolTypeChecker.py)]
                                         │
                                         ▼
              ┌──────────────────────────┴──────────────────────────┐
              ▼                                                     ▼
 [Step 1: Preconditions]                             [Step 2: Program Transitions]
  • SSA & Z3 Translation                              • AssignStmt / Phi Nodes -> Z3_ρ
  • Vacuous Proof Detection                           • WhileStmt -> verify_loop_transition()
    (solver.check() == unsat?)                        • CallSiteCheck -> Proved via Cloned Solver
              │                                       • AssertStmt -> Proved via Cloned Solver
              │                                       • FactStmt -> Consistency Check
              └──────────────────────────┬──────────────────────────┘
                                         ▼
                         [Step 3: Postconditions Check]
                          • Cloned Solver (post_solver)
                          • Assert Not(Combined_Postconditions)
                                         │
                                         ▼
                           [Step 4: Verification Verdict]
                       unsat -> ✅ PROVED | sat -> ❌ INVALID
```

---

## 2. Global Execution Flow & Verification Phases

### `main()`
* **Purpose:** The primary entry point that executes the complete verification workflow from command-line argument parsing to the final SMT theorem proving verdict.
* **Phase-by-Phase Technical Breakdown:**

---

### Phase 1: CLI Argument Parsing & Grammar Loading
* **Behavior:**
  * Validates that a filename argument was provided via `sys.argv[1]`; otherwise prints usage instructions and exits.
  * Reads the target specification program from `<filename>` and the LALR(1) grammar definition from `core/toolGrammar.lark`.
  * Instantiates the Lark parser bridge:
    ```python
    bridge_parser = Lark(grammar, start='start', parser='lalr', debug=True)
    ```

---

### Phase 2: AST Construction & Type Environment Building
* **Behavior:**
  * **Parsing:** Invokes `bridge_parser.parse(code)` to generate a Lark concrete syntax tree.
  * **AST Transformation:** Passes the tree through `Z3Transformer().transform(tree)` to produce the top-level `Program` AST node.
  * **Symbol Table Populating:** Instantiates `env = TypeEnvironment()` and executes `env.build(ast.declarations)` to register all variables, structs, constants, invisible variables, oracles, environments, and traces.

---

### Phase 3: Static & Linear Type Checking
* **Behavior:**
  * Instantiates `checker = TypeChecker(env)` and calls `checker.check_program(ast)`.
  * Enforces static type compatibility, operator rules, constant immutability, and substructural linear resource ownership (ensuring no use-after-free or memory leaks occur across `specProgram`).
  * **Linearity Toggling:** After static verification succeeds, sets `checker.enforce_linearity = False`.
  * *Reasoning:* Once the program is statically proven to be memory-safe, linearity checks are disabled so downstream Z3 translation can repeatedly reference linear struct variables in SSA formulas without triggering consumption exceptions.

---

### Phase 4: Z3 Engine & Timeline Initialization
* **Behavior:**
  * Instantiates the SMT backend: `translator = Z3Translator(env)`.
  * Creates the primary baseline solver: `solver = z3.Solver(ctx=translator.z3_ctx)` with a timeout of `30,000` ms (30 seconds).
  * Initializes `timeline_facts = []`: A Python list tracking every mathematically established formula in chronological order. This list is injected into cloned sandboxed solvers when proving assertions and postconditions.

---

### Phase 5: Step 1 — SSA Preconditions & Vacuous Proof Detection
* **Behavior:**
  * Instantiates the Single Static Assignment engine: `ssa_engine = SSATransformer(env)`.
  * Iterates across `ast.preconditions`:
    1. Transforms each formula into SSA form via `ssa_engine.transform_expr(pre)`.
    2. Translates the SSA formula into a Z3 SMT term via `translator.translate_expr(ssa_pre, checker)`.
    3. Asserts the term into `solver.add(z3_pre)` and appends it to `timeline_facts`.
  * **Vacuous Proof Detection (`solver.check() == z3.unsat`):**  
    Immediately checks whether the initial preconditions are satisfiable. If `unsat`, the initial state is mathematically impossible (contradictory preconditions). The harness aborts with a **Vacuous Proof Error** to prevent meaningless verification results where `False` implies anything.

---

### Phase 6: Step 2 — Program Transition Processing
* **Behavior:**  
  Generates the complete sequence of SSA program formulas by calling:
  ```python
  transition_items = ssa_engine.generate_transition_predicate(ast.specProgram)
  ```
  Iterates through `transition_items` and dispatches execution across **5 distinct verification handlers**:

#### 1. Inductive Loop Verification (`LoopTransition`)
* **Trigger:** When `item` is an instance of `LoopTransition` (generated by `WhileStmt`).
* **Action:**
  * Invokes `translator.verify_loop_transition(item, checker, solver)`, which uses push/pop sandboxing to prove base-case ($P(0)$) and inductive step ($P(k) \implies P(k+1)$) safety.
  * If the loop verifier returns `False`, prints an error and aborts (`exit(1)`).
  * If proved safe, translates `item.inv_read` and `z3.Not(item.cond_read)` and appends both to `timeline_facts`, establishing that after loop termination, the invariant holds and the loop condition is false.

#### 2. Oracle Call-Site Precondition Verification (`CallSiteCheck`)
* **Trigger:** When `item` is a `CallSiteCheck` (wrapping an oracle's grounded `assumes` contract).
* **Action:**
  * Uses **proof-by-falsification** in an isolated cloned solver:
    1. Instantiates `check_solver = z3.Solver(ctx=translator.z3_ctx)` with a 30-second timeout.
    2. Asserts all historical facts: `check_solver.add(timeline_facts)`.
    3. Asserts the **negation** of the call-site assumption: `check_solver.add(z3.Not(z3_formula))`.
  * **Verdict Evaluation:**
    * If `check_solver.check() == z3.sat`: A counter-example exists where the caller violates the oracle's precondition. Logs the model and aborts (`exit(1)`).
    * If `z3.unknown`: Aborts due to solver indecision.
    * If `z3.unsat`: ✅ Call-Site Check Passed. Asserts `z3_formula` into the main `solver` and `timeline_facts`.

#### 3. Axiomatic Fact Injection (`FactStmt`)
* **Trigger:** When `item` is a `FactStmt`.
* **Action:**
  * Translates `item.formula` and asserts it directly into `solver` and `timeline_facts`.
  * **Mid-Program Contradiction Check:** Evaluates `solver.check() == z3.unsat`. If `unsat`, the newly asserted fact contradicts the established program timeline. Logs a compilation error and aborts (`exit(1)`).

#### 4. Inline Assertion Verification (`AssertStmt`)
* **Trigger:** When `item` is an `AssertStmt`.
* **Action:**
  * Proves the assertion valid against the current timeline using an isolated cloned solver (`check_solver`):
    1. Asserts `timeline_facts` + `z3.Not(z3_formula)`.
    2. If `sat`: The assertion can be violated. Logs the counter-example model and aborts (`exit(1)`).
    3. If `unknown`: Aborts due to solver timeout/indecision.
    4. If `unsat`: ✅ Assertion Proved. Asserts `z3_formula` into `solver` and `timeline_facts` so downstream code can rely on it.

#### 5. Standard SSA Equations (Assignments & $\Phi$ Nodes)
* **Trigger:** Any standard mathematical expression (`BinaryExpr`, `TernaryExpr`, etc.) representing assignments (`lvalue_1 == rhs`) or conditional $\Phi$ merges.
* **Action:** Translates the formula via `translator.translate_expr(item, checker)`, asserts it into `solver.add(z3_formula)`, and appends it to `timeline_facts`.

---

### Phase 7: Step 3 — SSA Postconditions & Proof-by-Falsification
* **Behavior:**
  * Iterates across `ast.postconditions`, transforms each into SSA form using `ssa_engine.transform_expr(post)`, and translates them to Z3 terms.
  * **Conjunction:** If multiple postconditions exist, combines them into a single conjunction: `combined_postconditions = z3.And(*postcondition_exprs)`.
  * **Negation for Falsification:** Constructs the falsification goal:
    ```python
    goal_to_falsify = z3.Not(combined_postconditions)
    ```
  * **Sandboxed Postcondition Solver:** Instantiates a final cloned solver (`post_solver`), asserts the complete program history (`post_solver.add(timeline_facts)`), and asserts `goal_to_falsify`.
  * *Mathematical Reasoning:* To prove that a property $P$ holds for *all* possible program executions, SMT verifiers check if $
eg P$ is satisfiable. If no execution can satisfy $
eg P$ (`unsat`), then $P$ is universally valid.

---

### Phase 8: Step 4 — Final Verdict Evaluation
* **Behavior:**
  * Evaluates `result = post_solver.check()` and logs the final verification verdict:

| Z3 Solver Result | Verification Verdict | Meaning & Output Behavior |
| :--- | :--- | :--- |
| `z3.unsat` | ✅ **VERDICT: PROVED** | No counter-example can exist. The postconditions are mathematically guaranteed to hold for all valid executions. |
| `z3.sat` | ❌ **VERDICT: INVALID** | A concrete execution trace violates the postconditions. Prints the Z3 counter-example model (`post_solver.model()`) showing exact variable assignments. |
| `z3.unknown` | ❓ **VERDICT: UNKNOWN** | Z3 timed out or could not decide satisfiability due to non-linear arithmetic or quantifier complexity. Prints `post_solver.reason_unknown()`. |

---

## 3. Sandboxed Verification Architecture Summary Table

| Verification Target | Solver Used | Assertions Injected | Pass Condition | Failure Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Vacuous Preconditions** | Main `solver` | Precondition formulas | `z3.sat` | Exits with Vacuous Proof Error (`exit(1)`) |
| **Loop Invariant Induction** | Main `solver` (push/pop) | Base case / Inductive step | `z3.unsat` | Exits after `verify_loop_transition()` logs model (`exit(1)`) |
| **Oracle Call-Site Check** | Cloned `check_solver` | `timeline_facts` + $
eg(	ext{assumes})$ | `z3.unsat` | Exits with Precondition Violated model (`exit(1)`) |
| **Mid-Program Facts** | Main `solver` | `timeline_facts` + Fact formula | `z3.sat` | Exits with Contradictory Fact Error (`exit(1)`) |
| **Inline Assertions** | Cloned `check_solver` | `timeline_facts` + $
eg(	ext{assert})$ | `z3.unsat` | Exits with Assertion Violated model (`exit(1)`) |
| **Program Postconditions** | Cloned `post_solver` | `timeline_facts` + $
eg(	ext{postconditions})$ | `z3.unsat` | Prints Counter-Example model or Unknown reason |
