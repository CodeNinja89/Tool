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
        
        else:
            raise NotImplementedError(f"Z3 Sort mapping for type {type_name} not implemented!")
        
        self.sort_cache[type_name] = sort

        return sort
    
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

    def get_z3_var(self, name: str, type_name: str) -> z3.ExprRef:
        # creates or retrieves a specific Z3 variable
        if name in self.var_cache:
            return self.var_cache[name]
        
        z3_sort = self.get_z3_sort(type_name)
        z3_var = z3.Const(name, z3_sort)
        self.var_cache[name] = z3_var
        return z3_var
    
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

            if left_is_null and not right_is_null:
                right_type = tc.get_expr_type(expr.right)
                z3_sort = self.get_z3_sort(right_type)
                null_cons = getattr(z3_sort, f"null_{right_type}")
                left_z3 = cast(z3.ExprRef, null_cons())
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
            oracle_def = self.env.get_oracles(expr.name)

            z3_args = []
            for i, arg in enumerate(expr.args):
                if isinstance(arg, Literal) and arg.value == "null":
                    # Look up the expected type from the Oracle's mathematical definition
                    expected_type = oracle_def.args[i].typeName
                    z3_sort = self.get_z3_sort(expected_type)
                    null_constructor = getattr(z3_sort, f"null_{expected_type}")
                    z3_args.append(cast(z3.ExprRef, null_constructor))
                else:
                    z3_args.append(self.translate_expr(arg, tc))
            
            if expr.name not in self.func_cache:
                domain_sorts = [self.get_z3_sort(arg.typeName) for arg in oracle_def.args]
                range_sort = self.get_z3_sort(oracle_def.retType)
                self.func_cache[expr.name] = z3.Function(expr.name, *domain_sorts, range_sort)
                
            z3_func = self.func_cache[expr.name]
            z3_call = z3_func(*z3_args)
            
            """ # Initialize our side-loading storage if it doesn't exist yet
            if not hasattr(self, 'instantiated_macros'):
                self.instantiated_macros = set()
                self.side_loaded_contracts = []
                
            # Use the Z3 string representation as a unique cache key (e.g., "is_acyclic(footprint_1)")
            call_sig = str(z3_call)
            
            # If we haven't generated the contract for these exact arguments yet:
            if call_sig not in self.instantiated_macros:
                # 1. CACHE IT FIRST! This breaks the infinite recursion.
                self.instantiated_macros.add(call_sig) 
                
                # 2. Ask the manager for the Find-and-Replace AST
                grounded_ast = self.oracle_manager.inline_oracle(expr)
                
                # 3. Translate the math. When it recursively hits the inner FuncCall, 
                # the cache will catch it and it will just safely return z3_call!
                z3_contract = self.translate_expr(grounded_ast, tc)
                
                # 4. Save the completed contract to be injected into the solver later
                self.side_loaded_contracts.append(z3_contract) """
                
            return cast(z3.ExprRef, z3_call)
        
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
