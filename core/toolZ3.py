import z3
from typing import Dict, Any, cast, List

from core.toolAst import *
from core.toolTypes import TypeEnvironment
from core.toolTypeChecker import TypeChecker
from core.toolOracles import OracleManager

class Z3Verifier(ASTVisitor):
    def __init__(self, env: TypeEnvironment, tc: TypeChecker):
        self.env = env
        self.tc = tc  # The visitor holds the type checker directly
        self.z3_ctx = z3.Context() 
        self.solver = z3.Solver(ctx=self.z3_ctx) # The core verifier engine
        
        self.sort_cache: Dict[str, z3.SortRef] = {}
        self.var_cache: Dict[str, z3.ExprRef] = {}
        self.func_cache: Dict[str, z3.FuncDeclRef] = {}

        self._register_structs() 
        self.oracle_manager = OracleManager(self.env)

    def get_z3_sort(self, type_name: str) -> z3.SortRef:
        """Retrieves or creates the Z3 SMT sort from a Tool type."""
        if type_name in self.sort_cache:
            return self.sort_cache[type_name]
        
        if type_name == "bool":
            sort = z3.BoolSort(ctx=self.z3_ctx)
        elif type_name == "int":
            sort = z3.IntSort(ctx=self.z3_ctx)
        elif type_name.startswith("seq["):
            inner_type_str = type_name[4:-1]
            inner_sort = self.get_z3_sort(inner_type_str)
            sort = z3.ArraySort(z3.IntSort(ctx=self.z3_ctx), inner_sort) 
        elif type_name in self.env.structs:
            raise Exception(f"Z3 Error: Struct {type_name} not registered!")
        else:
            raise NotImplementedError(f"Z3 Sort mapping for type {type_name} not implemented!")
        
        self.sort_cache[type_name] = sort
        return sort
    
    # ==========================================
    # Z3 ALGEBRAIC DATATYPE (ADT) ARCHITECTURE
    # ==========================================
    # Unlike languages with memory addresses (C/Java), Z3 has no concept of a 
    # universal "null pointer" (e.g., 0x00000000). Instead, structs must be 
    # modeled as strict Algebraic Datatypes with mathematically disjoint states.
    #
    # For every user-defined struct (e.g., 'BST'), we declare TWO constructors:
    # 
    # 1. The Data Constructor (e.g., 'mk_BST'): 
    #    Takes arguments mapping to the struct's fields. Z3 automatically attaches 
    #    accessors (e.g., '.val', '.left') exclusively to this constructor.
    # 
    # 2. The Null Constructor (e.g., 'null_BST'):
    #    Takes zero arguments. This represents the "empty shape" of the struct.
    #
    # --- The Mathematical Guarantees ---
    # By defining multiple constructors on a single Z3 Datatype, we get three 
    # automatic axioms from the SMT solver:
    #   A) Mutually Exclusive: An object is strictly either 'mk_BST' OR 'null_BST'.
    #      (e.g., mk_BST(x,y,z) != null_BST() is automatically proven True).
    #   B) Recognizers: Z3 secretly generates boolean checks (is_mk_BST(t) and 
    #      is_null_BST(t)) to test which state an object is currently in.
    #   C) Safe Access: Accessing a field (t.val) on a 'null_BST' is mathematically
    #      undefined, forcing the verifier to prove the object is NOT null before 
    #      evaluating its fields.
    # ==========================================

    def _register_structs(self):
        """Translates user-defined Tool structs into Z3 Algebraic Datatypes."""
        for struct_name, fields in self.env.structs.items():
            z3_datatype = z3.Datatype(struct_name, ctx=self.z3_ctx)
            self.sort_cache[struct_name] = cast(z3.SortRef, z3_datatype)

            constructor_name = f"mk_{struct_name}"
            field_declarations = []

            for field_name, field_type_str in fields.items():
                field_sort = self.get_z3_sort(field_type_str)
                field_declarations.append((field_name, field_sort)) 

            z3_datatype.declare(constructor_name, *field_declarations)
            z3_datatype.declare(f"null_{struct_name}")
            
            sort = z3_datatype.create()
            self.sort_cache[struct_name] = sort

    def get_z3_var(self, name: str, type_name: str) -> z3.ExprRef:
        """Creates or retrieves a specific Z3 symbolic variable."""
        if name in self.var_cache:
            cached_var = self.var_cache[name]
            if cached_var.sort() == self.get_z3_sort(type_name):
                return cached_var
                
        z3_sort = self.get_z3_sort(type_name)
        z3_var = z3.Const(name, z3_sort)
        self.var_cache[name] = z3_var
        return z3_var
        
    def verify_program(self, program: Program) -> bool:
        """The main entry point for the verifier."""
        # This triggers the double-dispatch traversal
        program.accept(self)
        return True # If it traverses without throwing an assertion error, it is verified.
    
    def visit_VarRef(self, node: VarRef) -> z3.ExprRef:
        """Translates a variable reference, handling SSA integer suffixes."""
        # Strip SSA suffix (e.g., 'x_1' -> 'x') to lookup the base type
        if '_' in node.name and node.name.rsplit('_', 1)[1].isdigit():
            base_name = node.name.rsplit('_', 1)[0]
        else:
            base_name = node.name
            
        var_type = self.env.get_var_type(base_name)
        if var_type is None:
            raise Exception(f"Type Error: Variable '{base_name}' not found in environment.")
            
        return self.get_z3_var(node.name, var_type)

    def visit_Literal(self, node: Literal) -> z3.ExprRef:
        """Translates raw boolean and mathematical literals."""
        if node.value == "true":
            return z3.BoolVal(True, ctx=self.z3_ctx)
        if node.value == "false":
            return z3.BoolVal(False, ctx=self.z3_ctx)
        
        # 'null' is a special mathematical state, not a universal pointer.
        # It must be handled by parent nodes (like BinaryExpr or FuncCall) 
        # which have the type context needed to pick the right empty constructor.
        if node.value == "null":
            raise Exception("Z3 Translation Error: Isolated 'null' literal cannot be translated. It lacks type context.")
            
        # Default to integer
        return z3.IntVal(int(node.value), ctx=self.z3_ctx)

    def visit_UnaryExpr(self, node: UnaryExpr) -> z3.ExprRef:
        """Translates single-operand expressions."""
        operand_z3 = node.operand.accept(self)
        
        # We cast to Any to satisfy Python's static type hinter for overloaded Z3 operators
        op_dyn = cast(Any, operand_z3)

        if node.op == '!': 
            return cast(z3.ExprRef, z3.Not(operand_z3))
        if node.op == '-': 
            return cast(z3.ExprRef, -op_dyn)
        if node.op == '~': 
            return cast(z3.ExprRef, ~op_dyn)

        raise NotImplementedError(f"Z3 Translation: Unary operator '{node.op}' not supported.")
    
    def visit_BinaryExpr(self, node: BinaryExpr) -> z3.ExprRef:
        """Translates binary operations and handles ADT null resolution."""
        left_is_null = isinstance(node.left, Literal) and node.left.value == "null"
        right_is_null = isinstance(node.right, Literal) and node.right.value == "null"

        # --- Z3 "NULL" RESOLUTION MAGIC ---
        # Z3 lacks a universal 'null', so we infer the type from the other side 
        # of the equation and fetch its specific empty constructor (e.g., 'null_BST').
        # IMPORTANT Z3 API QUIRK: Zero-argument datatype constructors are automatically 
        # evaluated into concrete constants (DatatypeRef) by the Python bindings. 
        # Do NOT add parentheses (e.g., null_constructor()) or Z3 will crash 
        # with "TypeError: 'DatatypeRef' object is not callable".

        if left_is_null and not right_is_null:
            right_type = self.tc.get_expr_type(node.right)
            z3_sort = self.get_z3_sort(right_type)
            null_cons = getattr(z3_sort, f"null_{right_type}")
            left_z3 = cast(z3.ExprRef, null_cons)
            right_z3 = node.right.accept(self)

        elif right_is_null and not left_is_null:
            left_type = self.tc.get_expr_type(node.left)
            z3_sort = self.get_z3_sort(left_type)
            null_cons = getattr(z3_sort, f"null_{left_type}")
            right_z3 = cast(z3.ExprRef, null_cons)
            left_z3 = node.left.accept(self)
            
        elif left_is_null and right_is_null:
            raise Exception("Cannot infer type of 'null == null'.")
            
        else:
            left_z3 = node.left.accept(self)
            right_z3 = node.right.accept(self)

        # Logical Operators
        if node.op == '&&': return cast(z3.ExprRef, z3.And(left_z3, right_z3))
        if node.op == '||': return cast(z3.ExprRef, z3.Or(left_z3, right_z3))
        
        # We cast to Any to prevent Python type-hinter errors during operator overloading
        l_dyn = cast(Any, left_z3)
        r_dyn = cast(Any, right_z3)

        # Relational Operators
        if node.op == '==': return cast(z3.ExprRef, (l_dyn == r_dyn))
        if node.op == '!=': return cast(z3.ExprRef, (l_dyn != r_dyn))
        if node.op == '<':  return cast(z3.ExprRef, (l_dyn < r_dyn))
        if node.op == '<=': return cast(z3.ExprRef, (l_dyn <= r_dyn))
        if node.op == '>':  return cast(z3.ExprRef, (l_dyn > r_dyn))
        if node.op == '>=': return cast(z3.ExprRef, (l_dyn >= r_dyn))
        
        # Arithmetic Operators
        if node.op == '+': return cast(z3.ExprRef, l_dyn + r_dyn)
        if node.op == '-': return cast(z3.ExprRef, l_dyn - r_dyn)
        if node.op == '*': return cast(z3.ExprRef, l_dyn * r_dyn)
        if node.op == '/': return cast(z3.ExprRef, l_dyn / r_dyn)
        if node.op == '%': return cast(z3.ExprRef, l_dyn % r_dyn)

        raise NotImplementedError(f"Z3 Translation: Binary operator '{node.op}' not supported.")

    def visit_TernaryExpr(self, node: TernaryExpr) -> z3.ExprRef:
        """Translates conditional expressions (cond ? true_expr : false_expr)."""
        cond_z3 = node.condition.accept(self)

        true_is_null = isinstance(node.true_expr, Literal) and node.true_expr.value == "null"
        false_is_null = isinstance(node.false_expr, Literal) and node.false_expr.value == "null"

        # --- TERNARY NULL RESOLUTION ---
        if true_is_null and not false_is_null:
            false_type = self.tc.get_expr_type(node.false_expr)
            z3_sort = self.get_z3_sort(false_type)
            null_cons = getattr(z3_sort, f"null_{false_type}")
            true_z3 = cast(z3.ExprRef, null_cons)
            false_z3 = node.false_expr.accept(self)
            
        elif false_is_null and not true_is_null:
            true_type = self.tc.get_expr_type(node.true_expr)
            z3_sort = self.get_z3_sort(true_type)
            null_cons = getattr(z3_sort, f"null_{true_type}")
            false_z3 = cast(z3.ExprRef, null_cons)
            true_z3 = node.true_expr.accept(self)
            
        elif true_is_null and false_is_null:
            raise Exception("Cannot infer return type of ternary expression where both branches are null.")
            
        else:
            true_z3 = node.true_expr.accept(self)
            false_z3 = node.false_expr.accept(self)

        return cast(z3.ExprRef, z3.If(cond_z3, true_z3, false_z3))
    
    def visit_Quantifier(self, node: Quantifier) -> z3.ExprRef:
        """Translates logic quantifiers using environment scope injection."""
        old_type = self.env.variables.get(node.bound_var)
        
        # 1. Inject the bound variable into the TypeEnvironment
        self.env.variables[node.bound_var] = node.var_type
        z3_bound_var = self.get_z3_var(node.bound_var, node.var_type)

        # 2. Visit the inner formula (VarRefs will now resolve correctly)
        inner_z3 = node.formula.accept(self)

        # 3. Clean up the environment so the bound variable doesn't leak
        if old_type is not None:
            self.env.variables[node.bound_var] = old_type
        else:
            del self.env.variables[node.bound_var]

        if node.bound_var in self.var_cache:
            del self.var_cache[node.bound_var]

        if node.quant_type == "forall":
            return cast(z3.ExprRef, z3.ForAll([z3_bound_var], inner_z3))
        elif node.quant_type == "exists":
            return cast(z3.ExprRef, z3.Exists([z3_bound_var], inner_z3))
            
        raise Exception(f"Unknown quantifier '{node.quant_type}'")

    def visit_FuncCall(self, node: FuncCall) -> z3.ExprRef:
        """Translates function calls, struct constructors, and recursive oracles."""
        # --- Intercept Struct Constructors ---
        if node.name.startswith("mk_") and node.name[3:] in self.env.structs:
            struct_name = node.name[3:]
            struct_fields = list(self.env.get_struct_fields(struct_name).values())
            
            z3_args = []
            for i, arg in enumerate(node.args):
                if isinstance(arg, Literal) and arg.value == "null":
                    z3_sort = self.get_z3_sort(struct_fields[i])
                    z3_args.append(cast(z3.ExprRef, getattr(z3_sort, f"null_{struct_fields[i]}")))
                else:
                    z3_args.append(arg.accept(self))
                    
            dt_sort = cast(z3.DatatypeSortRef, self.get_z3_sort(struct_name))
            return cast(z3.ExprRef, dt_sort.constructor(0)(*z3_args))

        # --- Oracle Resolution ---
        oracle_def = self.env.get_oracles(node.name)
        
        # 1. Translate concrete arguments
        z3_args = []
        for i, arg in enumerate(node.args):
            if isinstance(arg, Literal) and arg.value == "null":
                expected_type = oracle_def.args[i].typeName
                z3_sort = self.get_z3_sort(expected_type)
                z3_args.append(cast(z3.ExprRef, getattr(z3_sort, f"null_{expected_type}")))
            else:
                z3_args.append(arg.accept(self))

        # 2. Compile Signature if not cached
        if node.name not in self.func_cache:
            domain_sorts = [self.get_z3_sort(arg.typeName) for arg in oracle_def.args]
            range_sort = self.get_z3_sort(oracle_def.retType)

            if self.oracle_manager.is_recursive(oracle_def):
                # Pre-cache to break infinite compilation loops
                z3_func = z3.RecFunction(node.name, *domain_sorts, range_sort)
                self.func_cache[node.name] = z3_func
                
                # Extract Returns clause
                returns_clause = next((c for c in oracle_def.clauses if isinstance(c, Returns)), None)
                if not returns_clause: 
                    raise Exception(f"Recursive oracle '{node.name}' missing Returns clause.")
                
                returns_expr = returns_clause.formula
                
                # 1. Explicitly narrow the type to satisfy the static checker
                if not isinstance(returns_expr, BinaryExpr) or returns_expr.op != '==':
                    raise Exception(f"Oracle '{node.name}' Returns clause must be an equality (e.g., {oracle_def.retName} == ...)")
                
                # 2. Strip the return variable to isolate the pure mathematical body
                if isinstance(returns_expr.left, VarRef) and returns_expr.left.name == oracle_def.retName:
                    body_ast = returns_expr.right
                elif isinstance(returns_expr.right, VarRef) and returns_expr.right.name == oracle_def.retName:
                    body_ast = returns_expr.left
                else:
                    raise Exception(f"Oracle '{node.name}' Returns clause must isolate the return variable '{oracle_def.retName}'.")
                
                # Sandboxed Body Translation
                old_env_vars, old_cache_vars, z3_bound_vars = {}, {}, []
                
                # Sandboxed Body Translation
                old_env_vars, old_cache_vars, z3_bound_vars = {}, {}, []
                for arg in oracle_def.args:
                    if arg.name in self.env.variables: old_env_vars[arg.name] = self.env.variables[arg.name]
                    if arg.name in self.var_cache: old_cache_vars[arg.name] = self.var_cache[arg.name]
                    self.env.variables[arg.name] = arg.typeName
                    z3_bound_vars.append(self.get_z3_var(arg.name, arg.typeName))

                z3_body = body_ast.accept(self)

                for arg in oracle_def.args:
                    if arg.name in old_env_vars: self.env.variables[arg.name] = old_env_vars[arg.name]
                    else: del self.env.variables[arg.name]
                    if arg.name in old_cache_vars: self.var_cache[arg.name] = old_cache_vars[arg.name]
                    elif arg.name in self.var_cache: del self.var_cache[arg.name]

                z3.RecAddDefinition(z3_func, z3_bound_vars, z3_body)
            else:
                self.func_cache[node.name] = z3.Function(node.name, *domain_sorts, range_sort)
        
        # 3. Execute Call
        return cast(z3.ExprRef, self.func_cache[node.name](*z3_args))

    def visit_FieldAccess(self, node: FieldAccess) -> z3.ExprRef:
        obj_z3 = node.obj.accept(self)
        obj_type = self.tc.get_expr_type(node.obj)

        if obj_type.startswith("seq[") and node.field == "length":
            length_func_name = f"Length_{obj_type}"
            if length_func_name not in self.func_cache:
                self.func_cache[length_func_name] = z3.Function(length_func_name, self.get_z3_sort(obj_type), z3.IntSort(ctx=self.z3_ctx))
            return cast(z3.ExprRef, self.func_cache[length_func_name](obj_z3))
            
        z3_sort = self.get_z3_sort(obj_type)
        return cast(z3.ExprRef, getattr(z3_sort, node.field)(obj_z3))

    def visit_StructUpdate(self, node: StructUpdate) -> z3.ExprRef:
        old_obj_z3 = node.obj.accept(self)
        new_val_z3 = node.new_value.accept(self)
        obj_type = self.tc.get_expr_type(node.obj)
        
        dt_sort = cast(z3.DatatypeSortRef, self.get_z3_sort(obj_type))
        constructor = dt_sort.constructor(0)
        
        constructor_args = []
        for f_name in self.env.get_struct_fields(obj_type).keys():
            if f_name == node.field:
                constructor_args.append(new_val_z3)
            else:
                constructor_args.append(getattr(dt_sort, f_name)(old_obj_z3))
                
        return cast(z3.ExprRef, constructor(*constructor_args))

    def visit_SeqAccess(self, node: SeqAccess) -> z3.ExprRef:
        seq_z3 = node.seq_obj.accept(self)
        idx_z3 = node.index.accept(self)
        return cast(z3.ExprRef, z3.Select(seq_z3, idx_z3))

    def visit_SeqUpdate(self, node: SeqUpdate) -> z3.ExprRef:
        seq_z3 = node.seq_obj.accept(self)
        idx_z3 = node.index.accept(self)
        val_z3 = node.new_value.accept(self)
        return cast(z3.ExprRef, z3.Store(seq_z3, idx_z3, val_z3))
    
    def visit_CallSiteCheck(self, node: CallSiteCheck) -> z3.ExprRef:
        """Unwraps and evaluates dynamically generated oracle preconditions."""
        return node.formula.accept(self)

    def visit_AssumesClause(self, node: AssumesClause) -> None:
        """Evaluates the precondition of an oracle."""
        formula_z3 = node.formula.accept(self)
        self.solver.add(formula_z3)

    def visit_Returns(self, node: Returns) -> None:
        """Evaluates the postcondition of a function."""
        formula_z3 = node.formula.accept(self)
        self.solver.add(formula_z3)

    def visit_AssignStmt(self, node: AssignStmt) -> None:
        """Translates an SSA assignment into a mathematical equality."""
        lval_z3 = node.lvalue.accept(self)
        expr_z3 = node.expr.accept(self)
        self.solver.add(lval_z3 == expr_z3)

    def visit_AssertStmt(self, node: AssertStmt) -> None:
        """Actively attempts to break a mathematical assertion."""
        formula_z3 = node.formula.accept(self)
        
        self.solver.push()
        self.solver.add(z3.Not(formula_z3))
        
        if self.solver.check() == z3.sat:
            print(f"\n--- [VERIFICATION FAILURE] ---")
            print(f"Assertion failed: {node.formula}")
            print("Counter-Model:")
            print(self.solver.model())
            self.solver.pop()
            raise Exception("Mathematical assertion does not hold.")
            
        self.solver.pop()
        # If it survives the check, it is proven true. Add it to the main timeline.
        self.solver.add(formula_z3)

    def visit_AssumeStmt(self, node: AssumeStmt) -> None:
        """Injects an axiomatic truth directly into the procedural timeline."""
        formula_z3 = node.formula.accept(self)
        self.solver.add(formula_z3)

    def visit_BlockStmt(self, node: BlockStmt) -> None:
        """Sequentially processes a block of statements."""
        # Because Z3 assertions are commutative conjuncts in the SMT engine, 
        # standard forward iteration perfectly matches the strongest postcondition state.
        for stmt in node.statements:
            stmt.accept(self)

    def visit_IfStmt(self, node: IfStmt) -> None:
        """
        Processes branching logic. In an SSA-driven formal framework, 
        state merging (Phi nodes) is handled by the SSA builder. 
        The verifier simply asserts the conditions driving the active blocks.
        """
        cond_z3 = node.condition.accept(self)
        
        # We push/pop to isolate the branch assertions from the main timeline,
        # relying on SSA Phi-functions (evaluated later in the block) to merge the reality.
        self.solver.push()
        self.solver.add(cond_z3)
        node.then_block.accept(self)
        self.solver.pop()
        
        if node.else_block:
            self.solver.push()
            self.solver.add(z3.Not(cond_z3))
            node.else_block.accept(self)
            self.solver.pop()

    def visit_WhileStmt(self, node: WhileStmt) -> None:
        """
        Raw While loops cannot be verified directly in SMT. 
        They must be transformed into LoopTransitions by an SSA pass first.
        """
        raise Exception("Z3 Verifier encountered an un-transformed WhileStmt. Run the SSA/Induction compiler pass first.")

    def visit_LoopTransition(self, node: LoopTransition) -> None:
        """
        Executes the 3-step Mathematical Induction proof for loops 
        using Z3 sandboxing.
        """
        inv_pre = node.inv_pre.accept(self)
        inv_read = node.inv_read.accept(self)
        inv_write = node.inv_write.accept(self)
        cond_read = node.cond_read.accept(self)

        # 1. Base Case: Does the invariant hold upon loop entry?
        self.solver.push()
        self.solver.add(z3.Not(inv_pre))
        if self.solver.check() == z3.sat:
            print("Loop Base Case Failure: Invariant does not hold upon entry!")
            print(self.solver.model())
            self.solver.pop()
            raise Exception("Loop Base Case Verification Failed")
        self.solver.pop()
        
        # 2. Inductive Step: Assume invariant and condition are true at start of iteration.
        self.solver.push()
        self.solver.add(inv_read)
        self.solver.add(cond_read)

        # Execute the loop body in this isolated timeline
        for f in node.body_formulas:
            f.accept(self)

        # Prove the invariant must mathematically hold at the end of the iteration
        self.solver.add(z3.Not(inv_write))
        if self.solver.check() == z3.sat:
            print("Loop Inductive Step Failure: Loop body does not maintain the invariant!")
            print(self.solver.model())
            self.solver.pop()
            raise Exception("Loop Inductive Step Verification Failed")
        self.solver.pop()
        
        # 3. Post-Condition: Inject the post-loop reality into the main program timeline
        self.solver.add(inv_read)          
        self.solver.add(z3.Not(cond_read))