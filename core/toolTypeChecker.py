from core.toolAst import *
from core.toolTypes import TypeEnvironment

NUMERIC_TYPES = {
    "int"
}

class TypeChecker:
    def __init__(self, env: TypeEnvironment):
        self.env = env
        self.delta = {} # track unconsumed resources (variables)
        self.enforce_linearity = True

    def get_expr_type(self, expr: ASTNode, is_refer: bool = False) -> str:
        if isinstance(expr, VarRef):
            name = expr.name
            if '_' in name and name.rsplit('_', 1)[1].isdigit():
                base_name = name.rsplit('_', 1)[0]
            else:
                base_name = name

            var_type = self.env.get_var_type(base_name)
            if self.enforce_linearity and var_type in self.env.linear_structs:
                if base_name in self.delta:
                    if not is_refer:
                        del self.delta[base_name]
                else:
                    raise Exception(f"Use-After-Free Error: Linear variable '{base_name}' was already consumed")
                
            return var_type
        
        elif isinstance(expr, Literal):
            if expr.value in ["true", "false"]:
                return "bool"
            if expr.value == "null": return "null" # wildcard type
            return "int" # fallback for mathematical integers
        
        elif isinstance(expr, BinaryExpr):
            left_type = self.get_expr_type(expr.left)
            right_type = self.get_expr_type(expr.right)

            # logical operators
            if expr.op in ['&&', '||']:
                if left_type != "bool" or right_type != "bool":
                    raise Exception(f"Type Error: '{expr.op}' expects booleans")
                return "bool"
            
            # relational operators
            if expr.op in ['==', '!=']:
                if left_type == "null" and right_type in self.env.structs: return "bool"
                if right_type == "null" and left_type in self.env.structs: return "bool"
                if left_type != right_type:
                    raise Exception(f"Type Error: Cannot compare '{left_type}' and '{right_type}")
                return "bool"
            
            if expr.op in ['<', '>', '<=', '>=']:
                if left_type not in NUMERIC_TYPES or right_type not in NUMERIC_TYPES:
                    raise Exception("Relational operators require numeric types")
                return "bool"
            
            # arithmetic and bitwise operations
            if expr.op in ['+', '-', '*', '/', '%', '&', '|', '^', '<<', '>>']:
                if left_type not in NUMERIC_TYPES and right_type not in NUMERIC_TYPES:
                    raise Exception(f"Operation {expr.op} cannot be used with non-numeric types")
                if left_type != right_type:
                    raise Exception(f"Type Error: Operator {expr.op} expects {left_type}")
                return left_type
            
        elif isinstance(expr, UnaryExpr):
            operand_type = self.get_expr_type(expr.operand)
            if expr.op == '!':
                if operand_type != "bool":
                    raise Exception("Type Error: '!' requires a boolean type")
                return "bool"
            if expr.op in ['-', '~']:
                if operand_type not in NUMERIC_TYPES:
                    raise Exception(f"Type Error: '{expr.op}' requires a numberic type, got '{operand_type}'")
                return operand_type
            
        elif isinstance(expr, TernaryExpr):
            # 1. Recursively get the types of both branches
            true_type = self.get_expr_type(expr.true_expr)
            false_type = self.get_expr_type(expr.false_expr)
            
            # 2. Handle 'null' wildcard resolution
            if true_type == "null" and false_type != "null":
                return false_type
            if false_type == "null" and true_type != "null":
                return true_type
            if true_type == "null" and false_type == "null":
                return "null"
                
            # 3. If both are concrete types, they must match
            if true_type != false_type:
                raise Exception(f"Type Error in Ternary: branches have mismatched types '{true_type}' and '{false_type}'")
                
            return true_type
            
        elif isinstance(expr, FuncCall):
            # --- Intercept implicitly generated struct constructors ---
            if expr.name.startswith("mk_") and expr.name[3:] in self.env.structs:
                struct_name = expr.name[3:]
                struct_fields = list(self.env.get_struct_fields(struct_name).values())
                
                if len(expr.args) != len(struct_fields):
                    raise Exception(f"Constructor {expr.name} expects {len(struct_fields)} args, got {len(expr.args)}")
                    
                for i, arg_expr in enumerate(expr.args):
                    arg_type = self.get_expr_type(arg_expr)
                    expected_type = struct_fields[i]
                    # 'null' can technically inhabit any struct type pointer
                    if arg_type != "null" and arg_type != expected_type:
                        raise Exception(f"Type Error: Arg {i} of {expr.name} expects {expected_type}, got {arg_type}")
                
                return struct_name # A constructor returns an instance of the struct!
            
            oracle = self.env.get_oracles(expr.name)
            if len(expr.args) != len(oracle.args):
                raise Exception(f"Oracle {expr.name} expects {len(oracle.args)} but got {len(expr.args)}")
            for i, arg_expr in enumerate(expr.args):
                is_refer_arg = oracle.args[i].is_refer
                arg_type = self.get_expr_type(arg_expr, is_refer_arg)
                expected_type = oracle.args[i].typeName
                if arg_type != expected_type:
                    raise Exception(f"Type Error: Arg {i} of {expr.name} expects {expected_type}, got {arg_type}")
            return oracle.retType
            
        elif isinstance(expr, FieldAccess):
            obj_type = self.get_expr_type(expr.obj, is_refer)

            # as per the grammar, a field access of the form <structName>.<fieldName>
            # if the struct has a field which is a sequence, then writing
            # <structName>.<fieldName>.length will be a problem because the parser will
            # think that <fieldName> is another struct. so, we must short circuit that
            # logic and simply return a uint32 for the length of a sequence.
            # this also means that the length of a sequence is always a 32-bit integer.

            if obj_type.startswith("seq[") and expr.field == "length":
                return "int"
            
            fields = self.env.get_struct_fields(obj_type)
            if expr.field not in fields:
                raise Exception(f"Struct {obj_type} has no field {expr.field}")
            return fields[expr.field]
        
        elif isinstance(expr, SeqAccess):
            seq_type = self.get_expr_type(expr.seq_obj)
            if not seq_type.startswith("seq["):
                raise Exception(f"Cannot index a non-sequence type {seq_type}")
            idx_type = self.get_expr_type(expr.index)
            if idx_type not in NUMERIC_TYPES:
                raise Exception(f"Sequence index must be numeric")
            
            inner_type = seq_type[4:-1]
            return inner_type
        
        elif type(expr).__name__ == "Quantifier":
            # Just return bool for now so the checker doesn't crash if it hits a forall/exists node
            print("HERE WE ARE!")
            return "bool"
        raise NotImplementedError(f"Type checking for {type(expr)} not implemented.")
    
    def _assert_type(self, expr: ASTNode, expected: str, msg: str):
        actual = self.get_expr_type(expr)
        if actual != expected:
            raise Exception(f"Type Error: {msg} (Got '{actual}', expected '{expected}')")
        
    def check_stmt(self, stmt: Stmt):
        if isinstance(stmt, AssignStmt):
            is_invisible_assign = False
            if isinstance(stmt.lvalue, VarRef):
                if self.env.is_constant(stmt.lvalue.name):
                    raise Exception(f"Type Error: Cannot assign to constant variable '{stmt.lvalue.name}'")
                base_name = stmt.lvalue.name
                if '_' in base_name and base_name.rsplit('_', 1)[1].isdigit():
                    base_name = base_name.rsplit('_', 1)[0]
                if base_name in self.env.invisible_vars:
                    is_invisible_assign = True

            # Evaluate RHS. If LHS is invisible, treat the RHS as a 'refer' so it isn't consumed!
            rhs_type = self.get_expr_type(stmt.expr, is_refer=is_invisible_assign)

            # replenish linear resources
            if isinstance(stmt.lvalue, VarRef):
                base_name = stmt.lvalue.name
                if '_' in base_name and base_name.rsplit('_', 1)[1].isdigit():
                    base_name = base_name.rsplit('_', 1)[0]
                lhs_type = self.env.get_var_type(base_name)
                if lhs_type != rhs_type:
                    raise Exception(f"Type Error in Assignment: Cannot assign {rhs_type} to {lhs_type}")
                
                # if we assign to a linear variable, it becomes available in Delta again
                if lhs_type in self.env.linear_structs and not is_invisible_assign:
                    self.delta[base_name] = lhs_type

            else:
                lhs_type = self.get_expr_type(stmt.lvalue)
                if lhs_type != rhs_type:
                    raise Exception(f"Type Error in Assignment: Cannot assign {rhs_type} to {lhs_type}")

        elif isinstance(stmt, AssertStmt):
            self._assert_type(stmt.formula, "bool", "Assert condition must be boolean.")

        elif isinstance(stmt, FactStmt):
            self._assert_type(stmt.formula, "bool", "Fact condition must be boolean.")

        elif isinstance(stmt, BlockStmt):
            for s in stmt.statements:
                self.check_stmt(s)
                
        elif isinstance(stmt, IfStmt):
            self._assert_type(stmt.condition, "bool", "If condition must be boolean.")
            delta_before = self.delta.copy()
            self.check_stmt(stmt.then_block)
            delta_then = self.delta.copy()
            self.delta = delta_before.copy()

            if stmt.else_block:
                self.check_stmt(stmt.else_block)
            
            delta_else = self.delta.copy()

            if delta_then != delta_else:
                raise Exception(f"Linear Type Error in If/Else block")
            
            self.delta = delta_then
                
        elif isinstance(stmt, WhileStmt):
            self._assert_type(stmt.condition, "bool", "While condition must be boolean.")
            if stmt.invariant:
                self._assert_type(stmt.invariant, "bool", "Loop invariant must be boolean.")
                
            delta_before = self.delta.copy()
            self.check_stmt(stmt.body)
            if self.delta != delta_before:
                raise Exception("Linear Type Error: While loop body permanently consumes resources!")

    def check_program(self, program: Program):
        # 1. Initialize Delta with global linear variables
        for var_name, var_type in self.env.variables.items():
            if var_type in self.env.linear_structs:
                self.delta[var_name] = var_type

        self.enforce_linearity = False

        for pre in program.preconditions:
            self._assert_type(pre, "bool", "PRECONDITION MUST BE BOOLEAN!")
        for post in program.postconditions:
            self._assert_type(post, "bool", "POSTCONDITIONS MUST BE BOOLEAN!")

        self.enforce_linearity = True
            
        for stmt in program.specProgram:
            if isinstance(stmt, Stmt):
                self.check_stmt(stmt)
                
        # Scope Exit: Anti-Leak Check
        if len(self.delta) > 0:
            leaked = ", ".join(self.delta.keys())
            raise Exception(f"Memory Leak Error: Linear variables [{leaked}] were never consumed.")
