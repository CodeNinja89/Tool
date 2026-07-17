import z3
from typing import Dict, Any, cast
from core.toolAst import *
from core.toolTypes import TypeEnvironment
from core.toolTypeChecker import *
from core.toolOracles import OracleManager

class Z3Translator:
    def __init__(self, env: TypeEnvironment):
        self.env = env
        self.z3_ctx = z3.Context() # clean Z3 context
        self.sort_cache: Dict[str, z3.SortRef] = {}
        self.var_cache: Dict[str, z3.ExprRef] = {}
        self.func_cache: Dict[str, z3.FuncDeclRef] = {}

        # Oracle definition bookkeeping.
        # These prevent duplicate RecAddDefinition calls and avoid infinite recursion
        # while compiling recursive oracle bodies.
        self.oracle_defs_added = set()
        self.oracle_defs_in_progress = set()

        self._register_structs() # register user-defined structs before anything else.
        self.oracle_manager = OracleManager(self.env)

    def get_z3_sort(self, type_name: str) -> z3.SortRef:
        # get the Z3 SMT sort from a Tool type
        if type_name in self.sort_cache:
            return self.sort_cache[type_name]
        
        # translate booleans
        if type_name == "bool":
            sort = z3.BoolSort(ctx=self.z3_ctx)

        # unbounded mathematical integers
        elif type_name == "int":
            sort = z3.IntSort(ctx=self.z3_ctx)

        # sequences
        elif type_name.startswith("seq["):
            inner_type_str = type_name[4:-1]
            inner_sort = self.get_z3_sort(inner_type_str)
            sort = z3.ArraySort(z3.IntSort(ctx=self.z3_ctx), inner_sort) # an array is a mapping from an index (mathematical integer) to a specific type
        
        elif type_name in self.env.structs:
            raise Exception(f"Z3 Error: Struct {type_name} not registered!")
        
        elif type_name == "timestep":
            sort = z3.IntSort(ctx=self.z3_ctx)
        
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
        # translate a struct in Tool to a Z3 data type
        for struct_name, fields in self.env.structs.items():
            z3_datatype = z3.Datatype(struct_name, ctx=self.z3_ctx)
            self.sort_cache[struct_name] = cast(z3.SortRef, z3_datatype)

            # create a constructor for the datatype
            constructor_name = f"mk_{struct_name}"

            # map the fields to the constructor
            field_declarations = []

            for field_name, field_type_str in fields.items():
                field_sort = self.get_z3_sort(field_type_str)
                field_declarations.append((field_name, field_sort)) # field accessor and it's type form a tuple

            z3_datatype.declare(constructor_name, *field_declarations)
            z3_datatype.declare(f"null_{struct_name}")
            sort = z3_datatype.create()
            self.sort_cache[struct_name] = sort

    def _find_patterns(self, expr: z3.ExprRef, bound_vars: list) -> list:
        """Heuristic to find array accesses to use as Z3 triggers."""
        patterns = []
        
        # 1. Handle standard applications (Functions, Operators, Selects)
        if z3.is_app(expr):
            # Check if this is a Select operation: footprint[i]
            if expr.decl().kind() == z3.Z3_OP_SELECT:
                # Select(Array, Index) -> index is the second child (index 1)
                if expr.num_args() > 1:
                    idx = expr.arg(1)
                    for bv in bound_vars:
                        if bv.eq(idx):
                            patterns.append(expr)
            
            # Recurse into children of the application
            for i in range(expr.num_args()):
                patterns.extend(self._find_patterns(expr.arg(i), bound_vars))
        
        # 2. Handle nested Quantifiers (where the "body" attribute lives)
        elif z3.is_quantifier(expr):
            # We must cast or use the quantifier-specific accessors
            # In Python Z3, quantifiers have a .body() method
            q_expr = cast(z3.QuantifierRef, expr)
            patterns.extend(self._find_patterns(q_expr.body(), bound_vars))
            
        return list(set(patterns))
    
    def _extract_rhs(self, expr: Expr, ret_name: str) -> Expr:
        # Traces are written as "s == expression". We need to extract the expression side.
        if isinstance(expr, BinaryExpr) and expr.op == '==':
            if isinstance(expr.left, VarRef) and expr.left.name == ret_name:
                return expr.right
            elif isinstance(expr.right, VarRef) and expr.right.name == ret_name:
                return expr.left
        raise Exception(f"Trace block must be formatted as '{ret_name} == <expression>'")
    
    def _extract_definition_body(self, expr: Expr, ret_name: str, kind: str = "definition") -> Expr:
        """
        Extract the body from a TOOL definition written as:

            ret == body

        or:

            body == ret

        Example:
            returns ok == !s.acquired || s.owner == 0;

        gives:
            !s.acquired || s.owner == 0
        """
        if isinstance(expr, BinaryExpr) and expr.op == '==':
            if isinstance(expr.left, VarRef) and expr.left.name == ret_name:
                return expr.right
            if isinstance(expr.right, VarRef) and expr.right.name == ret_name:
                return expr.left

        raise Exception(
            f"{kind} must be formatted as '{ret_name} == <expression>'"
        )

    def _translate_isolated_null(self, ret_type: str) -> z3.ExprRef:
        """
        Translate a bare TOOL null literal when the expected return type is known.
        """
        if ret_type not in self.env.structs:
            raise Exception(
                f"Cannot translate bare null for non-struct return type '{ret_type}'"
            )

        z3_sort = self.get_z3_sort(ret_type)
        null_constructor = getattr(z3_sort, f"null_{ret_type}")
        return cast(z3.ExprRef, null_constructor)

    def get_z3_var(self, name: str, type_name: str) -> z3.ExprRef:
        # creates or retrieves a specific Z3 variable
        if name in self.var_cache:
            cached_var = self.var_cache[name]
            # Ensure the cached variable actually matches the requested type!
            if cached_var.sort() == self.get_z3_sort(type_name):
                return cached_var
                
        # If not cached, OR if the type mismatched (shadowing), create a new one
        z3_sort = self.get_z3_sort(type_name)
        z3_var = z3.Const(name, z3_sort)
        self.var_cache[name] = z3_var
        return z3_var
    
    def _compile_oracle_definition(self, oracle_def: FunctionDef, tc: TypeChecker) -> z3.FuncDeclRef:
        """
        Compile a TOOL oracle into a Z3 definition.

        Important:
        - This is used for both recursive and non-recursive oracles.
        - Non-recursive oracles must not become uninterpreted functions.
        - The Z3 function shell is cached before translating the body so that
        recursive calls inside the body resolve to the same function.
        """
        oracle_name = oracle_def.name

        # Already fully defined.
        if oracle_name in self.oracle_defs_added:
            return self.func_cache[oracle_name]

        # Recursive call while compiling this oracle body.
        # Return the existing shell.
        if oracle_name in self.oracle_defs_in_progress:
            if oracle_name not in self.func_cache:
                raise Exception(
                    f"Internal error: oracle '{oracle_name}' is in progress but has no Z3 shell."
                )
            return self.func_cache[oracle_name]

        domain_sorts = [self.get_z3_sort(arg.typeName) for arg in oracle_def.args]
        range_sort = self.get_z3_sort(oracle_def.retType)

        # Create the Z3 function shell first.
        # RecFunction is fine for both recursive and non-recursive definitions.
        if oracle_name not in self.func_cache:
            print(f"DEBUG: Compiling TOOL oracle definition for '{oracle_name}'")
            self.func_cache[oracle_name] = z3.RecFunction(
                oracle_name,
                *domain_sorts,
                range_sort
            )

        z3_func = self.func_cache[oracle_name]

        returns_expr = None
        for clause in oracle_def.clauses:
            if isinstance(clause, Returns):
                returns_expr = clause.formula
                break

        if returns_expr is None:
            raise Exception(f"Oracle '{oracle_name}' is missing a returns clause.")

        body_ast = self._extract_definition_body(
            returns_expr,
            oracle_def.retName,
            kind=f"oracle '{oracle_name}'"
        )

        self.oracle_defs_in_progress.add(oracle_name)

        MISSING = object()
        old_env_vars = {}
        old_cache_vars = {}
        z3_bound_vars = []

        try:
            for arg in oracle_def.args:
                arg_name = arg.name
                arg_type = arg.typeName

                old_env_vars[arg_name] = self.env.variables.get(arg_name, MISSING)
                old_cache_vars[arg_name] = self.var_cache.get(arg_name, MISSING)

                self.env.variables[arg_name] = arg_type

                # Use oracle-scoped Z3 names to avoid accidental collisions with
                # global variables or parameters of other oracle definitions.
                z3_arg = z3.Const(
                    f"__{oracle_name}_{arg_name}",
                    self.get_z3_sort(arg_type)
                )

                self.var_cache[arg_name] = z3_arg
                z3_bound_vars.append(z3_arg)

            if isinstance(body_ast, Literal) and body_ast.value == "null":
                z3_body = self._translate_isolated_null(oracle_def.retType)
            else:
                z3_body = self.translate_expr(body_ast, tc)

            z3.RecAddDefinition(z3_func, z3_bound_vars, z3_body)

            self.oracle_defs_added.add(oracle_name)
            return z3_func

        finally:
            for arg in oracle_def.args:
                arg_name = arg.name

                old_env = old_env_vars[arg_name]
                if old_env is MISSING:
                    self.env.variables.pop(arg_name, None)
                else:
                    self.env.variables[arg_name] = old_env

                old_cache = old_cache_vars[arg_name]
                if old_cache is MISSING:
                    self.var_cache.pop(arg_name, None)
                else:
                    self.var_cache[arg_name] = old_cache

            self.oracle_defs_in_progress.discard(oracle_name)
    
    def translate_expr(self, expr: ASTNode, tc: TypeChecker) -> z3.ExprRef:
        # recursively translate an AST expressions into a Z3 expression

        if isinstance(expr, LoopTransition): # pass loop transition to the main harness. 
            # the type: ignore comment keeps the python hinter happy
            # we cannot use a cast here because we are passing the ASTNode directly
            return expr # type: ignore

        if isinstance(expr, VarRef):
            # we use the TypeChecker to tell use what type of this SSA variable is
            if '_' in expr.name and expr.name.rsplit('_', 1)[1].isdigit():
                base_name = expr.name.rsplit('_', 1)[0]
            else:
                base_name = expr.name
            var_type = self.env.get_var_type(base_name)
            return self.get_z3_var(expr.name, var_type)
        
        elif isinstance(expr, Literal):
            if expr.value == "true":
                return z3.BoolVal(True, ctx=self.z3_ctx)
            elif expr.value == "false":
                return z3.BoolVal(False, ctx=self.z3_ctx)
            else:
                val_type = tc.get_expr_type(expr)
                z3_sort = self.get_z3_sort(val_type)
                return z3.IntVal(int(expr.value), ctx=self.z3_ctx)
                
        elif isinstance(expr, BinaryExpr):
            left_is_null = isinstance(expr.left, Literal) and expr.left.value == "null"
            right_is_null = isinstance(expr.right, Literal) and expr.right.value == "null"

            # --- Z3 "NULL" RESOLUTION MAGIC ---
            # Z3 lacks a universal 'null', so we infer the type from the other side 
            # of the equation and fetch its specific empty constructor (e.g., 'null_BST').
            # IMPORTANT Z3 API QUIRK: Zero-argument datatype constructors are automatically 
            # evaluated into concrete constants (DatatypeRef) by the Python bindings. 
            # Do NOT add parentheses (e.g., null_constructor()) or Z3 will crash 
            # with "TypeError: 'DatatypeRef' object is not callable".

            if left_is_null and not right_is_null:
                right_type = tc.get_expr_type(expr.right)
                z3_sort = self.get_z3_sort(right_type)
                null_cons = getattr(z3_sort, f"null_{right_type}")
                left_z3 = cast(z3.ExprRef, null_cons)
                right_z3 = self.translate_expr(expr.right, tc)

            elif right_is_null and not left_is_null:
                left_type = tc.get_expr_type(expr.left)
                z3_sort = self.get_z3_sort(left_type)
                null_constructor = getattr(z3_sort, f"null_{left_type}")
                right_z3 = cast(z3.ExprRef, null_constructor)
                left_z3 = self.translate_expr(expr.left, tc)
                
            else:
                left_z3 = self.translate_expr(expr.left, tc)
                right_z3 = self.translate_expr(expr.right, tc)

            if expr.op == '&&': 
                return cast(z3.ExprRef, z3.And(left_z3, right_z3))
            if expr.op == '||':
                return cast(z3.ExprRef, z3.Or(left_z3, right_z3))
            
            left_type = tc.get_expr_type(expr.left)
            is_unsigned = left_type.startswith("uint")
            
            # time for unsigned math
            l_dyn = cast(Any, left_z3)
            r_dyn = cast(Any, right_z3)

            if expr.op == '==': 
                return cast(z3.ExprRef, (l_dyn == r_dyn))
            if expr.op == '!=': return cast(z3.ExprRef, (l_dyn != r_dyn))
            if expr.op == '<':  
                return cast(z3.ExprRef, (l_dyn < r_dyn))
            if expr.op == '<=':
                return cast(z3.ExprRef, (l_dyn <= r_dyn))
            if expr.op == '>':
                return cast(z3.ExprRef, (l_dyn > r_dyn))
            if expr.op == '>=': 
                return cast(z3.ExprRef, (l_dyn >= r_dyn))
            
            # arithmetic expressions
            if expr.op == '+': return cast(z3.ExprRef, l_dyn + r_dyn)
            if expr.op == '-': return cast(z3.ExprRef, l_dyn - r_dyn)
            if expr.op == '*': return cast(z3.ExprRef, l_dyn * r_dyn)

            if expr.op == '/': 
                return cast(z3.ExprRef, (l_dyn / r_dyn))
            if expr.op == '%': 
                return cast(z3.ExprRef, (l_dyn % r_dyn))
            raise NotImplementedError(f"Cannot convert {expr.op} to Z3")
        
        elif isinstance(expr, Quantifier):
            # scope injection
            old_type = self.env.variables.get(expr.bound_var)
            # now we insert the bound variable into the global TypeEnvironment
            # so the inner formula VarRefs can resolve it's type
            self.env.variables[expr.bound_var] = expr.var_type

            # create a specific Z3 Const for this bound variable
            z3_bound_var = self.get_z3_var(expr.bound_var, expr.var_type)

            # recursively translate the inner formula. When it hits VarRef('i')
            # the existing logic will find the injected variable
            inner_z3 = self.translate_expr(expr.formula, tc)
            found_patterns = self._find_patterns(inner_z3, [z3_bound_var])
            print(f"DEBUG: Found {len(found_patterns)} patterns for {expr.bound_var}")

            # now, cleanup. We have to remove the bound variable from the scope
            # otherwise, the bound variable can act as a normal variable and may
            # cause a name collision.

            if old_type is not None:
                self.env.variables[expr.bound_var] = old_type
            else:
                del self.env.variables[expr.bound_var]

            if expr.bound_var in self.var_cache:
                del self.var_cache[expr.bound_var]

            z3_patterns = [[p] for p in found_patterns if z3.is_expr(p)]

            # crete the Z3 formula
            if expr.quant_type == "forall":
                return cast(z3.ExprRef, z3.ForAll([z3_bound_var], inner_z3, patterns=found_patterns))
            elif expr.quant_type == "exists":
                return cast(z3.ExprRef, z3.Exists([z3_bound_var], inner_z3, patterns=found_patterns))
            else:
                raise Exception("Unknown quantifier")
            
        elif isinstance(expr, TernaryExpr):
            cond_z3 = self.translate_expr(expr.condition, tc)

            true_is_null = isinstance(expr.true_expr, Literal) and expr.true_expr.value == "null"
            false_is_null = isinstance(expr.false_expr, Literal) and expr.false_expr.value == "null"

            # --- Z3 TERNARY NULL RESOLUTION MAGIC ---
            if true_is_null and not false_is_null:
                # Infer the type from the false branch
                false_type = tc.get_expr_type(expr.false_expr)
                z3_sort = self.get_z3_sort(false_type)
                null_constructor = getattr(z3_sort, f"null_{false_type}")
                true_z3 = cast(z3.ExprRef, null_constructor)
                false_z3 = self.translate_expr(expr.false_expr, tc)
                
            elif false_is_null and not true_is_null:
                # Infer the type from the true branch
                true_type = tc.get_expr_type(expr.true_expr)
                z3_sort = self.get_z3_sort(true_type)
                null_constructor = getattr(z3_sort, f"null_{true_type}")
                false_z3 = cast(z3.ExprRef, null_constructor)
                true_z3 = self.translate_expr(expr.true_expr, tc)
                
            elif true_is_null and false_is_null:
                raise Exception("Cannot infer type of null in ternary expression where both branches are null.")
                
            else:
                # Standard translation if neither branch is a raw null literal
                true_z3 = self.translate_expr(expr.true_expr, tc)
                false_z3 = self.translate_expr(expr.false_expr, tc)

            return cast(z3.ExprRef, z3.If(cond_z3, true_z3, false_z3))
        
        elif isinstance(expr, UnaryExpr):
            operand_z3 = self.translate_expr(expr.operand, tc)
            op_dyn = cast(Any, operand_z3)

            if expr.op == '!': return cast(z3.ExprRef, z3.Not(operand_z3))
            if expr.op == '-': return cast(z3.ExprRef, -op_dyn)
            if expr.op == '~': return cast(z3.ExprRef, ~op_dyn)

            raise NotImplementedError(f"Cannot convert unary operator {expr.op} to Z3")

        elif isinstance(expr, SeqAccess):
            seq_z3 = self.translate_expr(expr.seq_obj, tc)
            idx_z3 = self.translate_expr(expr.index, tc)
            return cast(z3.ExprRef, z3.Select(seq_z3, idx_z3))

        elif isinstance(expr, SeqUpdate):
            seq_z3 = self.translate_expr(expr.seq_obj, tc)
            idx_z3 = self.translate_expr(expr.index, tc)
            val_z3 = self.translate_expr(expr.new_value, tc)
            return cast(z3.ExprRef, z3.Store(seq_z3, idx_z3, val_z3))
        
        elif isinstance(expr, FuncCall):
            # --- NEW: Intercept Struct Constructors ---
            if expr.name.startswith("mk_") and expr.name[3:] in self.env.structs:
                struct_name = expr.name[3:]
                struct_fields = list(self.env.get_struct_fields(struct_name).values())
                
                z3_args = []
                for i, arg in enumerate(expr.args):
                    if isinstance(arg, Literal) and arg.value == "null":
                        expected_type = struct_fields[i]
                        z3_sort = self.get_z3_sort(expected_type)
                        null_constructor = getattr(z3_sort, f"null_{expected_type}")
                        z3_args.append(cast(z3.ExprRef, null_constructor))
                    else:
                        z3_args.append(self.translate_expr(arg, tc))
                        
                dt_sort = cast(z3.DatatypeSortRef, self.get_z3_sort(struct_name))
                # constructor(0) gets the main 'mk_Struct' constructor we defined
                constructor = dt_sort.constructor(0) 
                return cast(z3.ExprRef, constructor(*z3_args))
            
            # --- Builtin: update_seq(seq, index, value) ---
            if expr.name == "update_seq":
                if len(expr.args) != 3:
                    raise Exception("update_seq expects exactly 3 arguments: update_seq(seq, index, value)")

                z3_arr = self.translate_expr(expr.args[0], tc)
                z3_idx = self.translate_expr(expr.args[1], tc)
                z3_val = self.translate_expr(expr.args[2], tc)

                return cast(z3.ExprRef, z3.Store(z3_arr, z3_idx, z3_val))


            # --- Builtin: mk_seq(default, v0, v1, v2, ...) ---
            elif expr.name == "mk_seq":
                if len(expr.args) == 0:
                    raise Exception("mk_seq requires at least one argument to determine the element type.")

                z3_values = [self.translate_expr(arg, tc) for arg in expr.args]

                ctx = self.z3_ctx

                # First argument is the default value for all indices.
                default_value = z3_values[0]
                elem_sort = default_value.sort()

                z3_arr = z3.K(z3.IntSort(ctx=ctx), default_value)

                # Optional remaining arguments initialize indices 0, 1, 2, ...
                # Example:
                #   mk_seq(7, 10, 20)
                # means:
                #   default 7, index 0 -> 10, index 1 -> 20
                for i, z3_val in enumerate(z3_values[1:]):
                    if z3_val.sort() != elem_sort:
                        raise Exception(
                            f"mk_seq element at index {i} has sort {z3_val.sort()}, expected {elem_sort}"
                        )

                    z3_arr = z3.Store(
                        z3_arr,
                        z3.IntVal(i, ctx=ctx),
                        z3_val
                    )

                return cast(z3.ExprRef, z3_arr)
            
            if self.env.is_env(expr.name):
                env_def = self.env.get_envs(expr.name)
                z3_args = []
                for i, arg in enumerate(expr.args):
                    if isinstance(arg, Literal) and arg.value == "null":
                        expected_type = env_def.args[i].typeName
                        z3_sort = self.get_z3_sort(expected_type)
                        null_constructor = getattr(z3_sort, f"null_{expected_type}")
                        z3_args.append(cast(z3.ExprRef, null_constructor))
                    else:
                        z3_args.append(self.translate_expr(arg, tc))

                if expr.name not in self.func_cache:
                    print(f"DEBUG: Compiling Native Z3 Function for '{expr.name}'")
                    domain_sorts = [self.get_z3_sort(arg.typeName) for arg in env_def.args]
                    range_sort = self.get_z3_sort(env_def.retType)
                    self.func_cache[expr.name] = z3.Function(expr.name, *domain_sorts, range_sort)

                z3_func = self.func_cache[expr.name]
                return cast(z3.ExprRef, z3_func(*z3_args))
            
            elif self.env.is_oracle(expr.name):
                oracle_def = self.env.get_oracles(expr.name)

                if len(expr.args) != len(oracle_def.args):
                    raise Exception(
                        f"Oracle {expr.name} expects {len(oracle_def.args)} args, got {len(expr.args)}"
                    )

                z3_func = self._compile_oracle_definition(oracle_def, tc)

                z3_args = []
                for i, arg in enumerate(expr.args):
                    if isinstance(arg, Literal) and arg.value == "null":
                        expected_type = oracle_def.args[i].typeName
                        z3_sort = self.get_z3_sort(expected_type)
                        null_constructor = getattr(z3_sort, f"null_{expected_type}")
                        z3_args.append(cast(z3.ExprRef, null_constructor))
                    else:
                        z3_args.append(self.translate_expr(arg, tc))

                return cast(z3.ExprRef, z3_func(*z3_args))
        
            elif self.env.is_trace(expr.name):
                trace_def = self.env.get_trace(expr.name)
    
                # Translate the concrete argument being passed to the trace
                z3_args = [self.translate_expr(expr.args[0], tc)]
                
                if expr.name not in self.func_cache:
                    print(f"DEBUG: Compiling Native Z3 Temporal Trace for '{expr.name}'")
                    domain_sort = self.get_z3_sort("timestep")
                    range_sort = self.get_z3_sort(trace_def.ret_type)
                    z3_func = z3.RecFunction(expr.name, domain_sort, range_sort)
                    self.func_cache[expr.name] = z3_func
                    
                    # Extract the pure functional mathematical bodies
                    init_ast = self._extract_rhs(trace_def.init_expr, trace_def.ret_name)
                    step_ast = self._extract_rhs(trace_def.step_expr, trace_def.ret_name)
                    
                    # Temporarily inject the temporal variable into the environment for translation
                    old_time_type = self.env.variables.get(trace_def.time_var)
                    self.env.variables[trace_def.time_var] = "timestep"
                    z3_bound_time = self.get_z3_var(trace_def.time_var, "timestep")
                    
                    # Translate the init body, explicitly handling isolated 'null' literals
                    if isinstance(init_ast, Literal) and init_ast.value == "null":
                        z3_sort = self.get_z3_sort(trace_def.ret_type)
                        null_constructor = getattr(z3_sort, f"null_{trace_def.ret_type}")
                        z3_init = cast(z3.ExprRef, null_constructor)
                    else:
                        z3_init = self.translate_expr(init_ast, tc)
                        
                    # Translate the step body, explicitly handling isolated 'null' literals
                    if isinstance(step_ast, Literal) and step_ast.value == "null":
                        z3_sort = self.get_z3_sort(trace_def.ret_type)
                        null_constructor = getattr(z3_sort, f"null_{trace_def.ret_type}")
                        z3_step = cast(z3.ExprRef, null_constructor)
                    else:
                        z3_step = self.translate_expr(step_ast, tc)
                    
                    # Clean up the environment
                    if old_time_type is not None:
                        self.env.variables[trace_def.time_var] = old_time_type
                    else:
                        del self.env.variables[trace_def.time_var]
                    if trace_def.time_var in self.var_cache:
                        del self.var_cache[trace_def.time_var]
                        
                    # Bind the init and step blocks together using a conditional
                    z3_body = z3.If(z3_bound_time == 0, z3_init, z3_step)
                    z3.RecAddDefinition(z3_func, [z3_bound_time], z3_body)       

                z3_func = self.func_cache[expr.name]
                return cast(z3.ExprRef, z3_func(*z3_args))
            
            else:
                raise Exception(f"Function '{expr.name}' is neither an oracle, an env function, nor a trace.")
                
        elif isinstance(expr, FieldAccess):
            obj_z3 = self.translate_expr(expr.obj, tc)
            obj_type = tc.get_expr_type(expr.obj)

            # handle the length of the sequence

            if obj_type.startswith("seq[") and expr.field == "length":
                # SMT arrays are infinite in length. We create an UF that maps
                # this specific sequence to an integer. This is ok because,
                # this is a specification language. We need to reason over the 
                # length of a sequence but may not need the actual length of the sequence.
                # for instance, a list can have 5 elements or 500; the axioms 
                # remain the same. We will reason about the list the same way.

                z3_array_sort = self.get_z3_sort(obj_type)
                length_func_name = f"Length_{obj_type}"

                if length_func_name not in self.func_cache:
                    self.func_cache[length_func_name] = z3.Function(length_func_name, z3_array_sort, z3.IntSort(ctx=self.z3_ctx))
                
                length_func = self.func_cache[length_func_name]
                return cast(z3.ExprRef, length_func(obj_z3))
            
            # handle struct field access
            z3_sort = self.get_z3_sort(obj_type)
            accessor = getattr(z3_sort, expr.field)
            return cast(z3.ExprRef, accessor(obj_z3))
        
        elif isinstance(expr, StructUpdate):
            old_obj_z3 = self.translate_expr(expr.obj, tc)
            new_val_z3 = self.translate_expr(expr.new_value, tc)

            obj_type = tc.get_expr_type(expr.obj)
            z3_sort = self.get_z3_sort(obj_type)
            dt_sort = cast(z3.DatatypeSortRef, z3_sort)
            struct_fields = self.env.get_struct_fields(obj_type)

            constructor = dt_sort.constructor(0)

            constructor_args = []
            for f_name in struct_fields.keys():
                if f_name == expr.field:
                    # Inject the new value for the updated field
                    constructor_args.append(new_val_z3)
                else:
                    # Copy the old value using the accessor for the other fields
                    accessor = getattr(dt_sort, f_name)
                    constructor_args.append(accessor(old_obj_z3))
                    
            return cast(z3.ExprRef, constructor(*constructor_args))
        
        elif isinstance(expr, CallSiteCheck):
            # A CallSiteCheck is just a wrapper for a boolean formula generated 
            # to verify an oracle's 'assumes' clause. We just unwrap it and translate it!
            return self.translate_expr(expr.formula, tc)
        
        raise NotImplementedError(f"Z3 translation for {type(expr)} not implemented!")
    
    def verify_loop_transition(self, expr: LoopTransition, tc: TypeChecker, 
                               solver: z3.Solver) -> bool:
        '''
            Verifies a loop using Mathematical Induction via Z3 push/pop sandboxing.
            Returns True if the loop is fully verified, False if an invariant fails.
        '''
        print("\n--- [LOOP VERIFIER] Analyzing WhileStmt ---")
        inv_pre = self.translate_expr(expr.inv_pre, tc)
        inv_read = self.translate_expr(expr.inv_read, tc)
        cond_read = self.translate_expr(expr.cond_read, tc)
        inv_write = self.translate_expr(expr.inv_write, tc)

        body_formulas = []
        for f in expr.body_formulas:
            body_formulas.append(self.translate_expr(f, tc))

        # verify if the invariant holds upon entry
        solver.push()
        solver.add(z3.Not(inv_pre))

        if solver.check() == z3.sat:
            print(f"invariant {inv_pre} does not hold upon entry!")
            print(solver.model())
            solver.pop()
            return False
        solver.pop()
        
        # verify the inductive step
        solver.push()
        
        # inductive assuption: The invariant and condition are true at the start of the iteration
        solver.add(inv_read)
        solver.add(cond_read)

        for f in body_formulas: # add the loop body to the solver... essentially, execute the loop
            solver.add(f)

        solver.add(z3.Not(inv_write)) # is it mathematically possible for the invariant to be false after the iteration completes?

        if solver.check() == z3.sat:
            print("Loop body does not maintain the invariant!")
            print(solver.model())
            solver.pop()
            return False
        
        solver.pop()
        # inject the post-loop reality directly into the main program's timeline
        solver.add(inv_read)          # Fact 1: The invariant holds
        solver.add(z3.Not(cond_read)) # Fact 2: The loop condition is false

        return True # placeholder to avoid red squiggles
