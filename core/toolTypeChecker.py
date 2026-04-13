from core.toolAst import *
from core.toolTypes import TypeEnvironment

NUMERIC_TYPES = {
    "int"
}

class TypeChecker:
    def __init__(self, env: TypeEnvironment):
        self.env = env

    def get_expr_type(self, expr: ASTNode) -> str:
        if isinstance(expr, VarRef):
            name = expr.name
            if '_' in name and name.rsplit('_', 1)[1].isdigit():
                base_name = name.rsplit('_', 1)[0]
            else:
                base_name = name
            return self.env.get_var_type(base_name)
        
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
            
        elif isinstance(expr, FuncCall):
            # --- NEW: Intercept implicitly generated struct constructors ---
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
                arg_type = self.get_expr_type(arg_expr)
                expected_type = oracle.args[i].typeName
                if arg_type != expected_type:
                    raise Exception(f"Type Error: Arg {i} of {expr.name} expects {expected_type}, got {arg_type}")
            return oracle.retType
            
        elif isinstance(expr, FieldAccess):
            obj_type = self.get_expr_type(expr.obj)

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
                raise Exception(f"Cannot inded a non-sequence type {seq_type}")
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
            # The LHS and RHS must have exactly the same type!
            lhs_type = self.get_expr_type(stmt.lvalue)
            rhs_type = self.get_expr_type(stmt.expr)
            if lhs_type != rhs_type:
                raise Exception(f"Type Error in Assignment: Cannot assign '{rhs_type}' to '{lhs_type}'. Explicit cast required.")
                
        elif isinstance(stmt, AssertStmt):
            self._assert_type(stmt.formula, "bool", "Assert condition must be boolean.")
            
        elif isinstance(stmt, BlockStmt):
            for s in stmt.statements:
                self.check_stmt(s)
                
        elif isinstance(stmt, IfStmt):
            self._assert_type(stmt.condition, "bool", "If condition must be boolean.")
            self.check_stmt(stmt.then_block)
            if stmt.else_block:
                self.check_stmt(stmt.else_block)
                
        elif isinstance(stmt, WhileStmt):
            self._assert_type(stmt.condition, "bool", "While condition must be boolean.")
            if stmt.invariant:
                self._assert_type(stmt.invariant, "bool", "Loop invariant must be boolean.")
            if stmt.measure:
                measure_type = self.get_expr_type(stmt.measure)
                if not ("int" in measure_type):
                    raise Exception(f"Type Error: Loop measure must be a numeric type, got '{measure_type}'.")
            self.check_stmt(stmt.body)

    def check_program(self, program: Program):
        for pre in program.preconditions:
            self._assert_type(pre, "bool", "PRECONDITION MUST BE BOOLEAN!")

        for post in program.postconditions:
            self._assert_type(post, "bool", "POSTCONDITIONS MUST BE BOOLEAN!")

        for stmt in program.specProgram:
            if isinstance(stmt, Stmt):
                self.check_stmt(stmt)
