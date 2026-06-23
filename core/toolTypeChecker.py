from typing import Any, Dict, Optional
from core.toolAst import *
from core.toolTypes import TypeEnvironment

class TypeChecker(ASTVisitor):
    def __init__(self, env: TypeEnvironment):
        self.env = env
        self.current_func_ret_type: Optional[str] = None
        
        # --- Linearity Tracking ---
        # Maps variable name to a boolean: True = consumed, False = available
        self.consumed_linear_vars: Dict[str, bool] = {}

    def check_program(self, program: Program) -> None:
        """Entry point to begin type checking."""
        program.accept(self)

    def visit_Program(self, node: Program) -> None:
        """Processes the structural layout of the file."""
        # 1. Register all structs first so variables can reference them
        for decl in node.declarations:
            if isinstance(decl, StructDef):
                decl.accept(self)
                
        # 2. Register variables and functions
        for decl in node.declarations:
            if not isinstance(decl, StructDef):
                decl.accept(self)
                
        # 3. Check Pre/Post conditions
        for pre in node.preconditions:
            if pre.accept(self) != "bool":
                raise Exception("Type Error: Preconditions must evaluate to a boolean expression.")
                
        for post in node.postconditions:
            if post.accept(self) != "bool":
                raise Exception("Type Error: Postconditions must evaluate to a boolean expression.")
                
        # 4. Check main imperative program block
        for stmt in node.specProgram:
            stmt.accept(self)
            
        # 5. Global Linearity Check
        for var_name, is_consumed in self.consumed_linear_vars.items():
            if not is_consumed:
                raise Exception(f"Linearity Error: Linear resource '{var_name}' was never consumed!")

    def visit_StructDef(self, node: StructDef) -> None:
        """Registers a struct and its linearity constraint in the environment."""
        self.env.register_struct(node.name, node.fields)
        if node.is_linear:
            # We assume TypeEnvironment has a set to track which structs are linear
            self.env.linear_structs.add(node.name)

    def visit_VarDecl(self, node: VarDecl) -> None:
        """Registers a variable and begins tracking it if it is linear."""
        if not self.env.is_valid_type(node.typeName):
            raise Exception(f"Type Error: Unknown type '{node.typeName}' for variable '{node.name}'.")
            
        self.env.register_var(node.name, node.typeName)
        
        if self.env.is_linear_type(node.typeName):
            self.consumed_linear_vars[node.name] = False

    def visit_InvisibleDecl(self, node: InvisibleDecl) -> None:
        if not self.env.is_valid_type(node.typeName):
            raise Exception(f"Type Error: Unknown type '{node.typeName}' for invisible var '{node.name}'.")
        self.env.register_var(node.name, node.typeName)

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        """Type checks an oracle definition within a local scope."""
        self.current_func_ret_type = node.retType
        
        # Push a local memory scope (assuming TypeEnvironment supports push_scope/pop_scope)
        self.env.push_scope()
        
        for arg in node.args:
            arg.accept(self)
            
        self.env.register_var(node.retName, node.retType)
        
        for clause in node.clauses:
            clause.accept(self)
            
        self.env.pop_scope()
        self.current_func_ret_type = None

    # ==========================================
    # --- PART 2: Expressions & Math Rules ---
    # ==========================================

    def get_expr_type(self, node: Expr) -> str:
        """Helper method to ensure we return a string from the visitor."""
        result = node.accept(self)
        if not isinstance(result, str):
            raise Exception(f"Compiler Error: Expression visitor returned {type(result)} instead of a string type.")
        return result

    def visit_VarRef(self, node: VarRef) -> str:
        """Looks up a variable and enforces single-consumption for linear resources."""
        # Handle SSA-style variables by stripping suffixes temporarily for type lookup
        base_name = node.name.rsplit('_', 1)[0] if ('_' in node.name and node.name.rsplit('_', 1)[1].isdigit()) else node.name
            
        var_type = self.env.get_var_type(base_name)
        if var_type is None:
            raise Exception(f"Type Error: Variable '{base_name}' used before assignment or not found in scope.")

        # --- Linearity Enforcement ---
        if self.env.is_linear_type(var_type):
            if self.consumed_linear_vars.get(base_name, False):
                raise Exception(f"Linearity Error: Linear resource '{base_name}' has already been consumed! It cannot be duplicated or reused.")
            # Mark it as consumed the moment it is evaluated
            self.consumed_linear_vars[base_name] = True
            
        return var_type

    def visit_Literal(self, node: Literal) -> str:
        if node.value in ("true", "false"):
            return "bool"
        if node.value == "null":
            return "null"  # Special mathematically ambiguous state
        return "int"

    def visit_BinaryExpr(self, node: BinaryExpr) -> str:
        left_type = self.get_expr_type(node.left)
        right_type = self.get_expr_type(node.right)

        # 1. Null Resolution for Equality
        if node.op in ("==", "!="):
            if left_type == "null" and right_type == "null":
                raise Exception("Type Error: Cannot compare two 'null' literals. Type is ambiguous.")
            if left_type == "null" or right_type == "null" or left_type == right_type:
                return "bool"
            raise Exception(f"Type Error: Cannot compare mismatching types '{left_type}' and '{right_type}'.")

        # 2. Logical Operators
        if node.op in ("&&", "||"):
            if left_type == "bool" and right_type == "bool":
                return "bool"
            raise Exception(f"Type Error: Logical operator '{node.op}' requires bools. Got {left_type} and {right_type}.")

        # 3. Arithmetic, Relational, and Bitwise (All require integers)
        if left_type != "int" or right_type != "int":
            raise Exception(f"Type Error: Operator '{node.op}' requires integers. Got {left_type} and {right_type}.")
        
        if node.op in ("+", "-", "*", "/", "%", "|", "^", "&", "<<", ">>"):
            return "int"
        if node.op in ("<", "<=", ">", ">="):
            return "bool"
            
        raise Exception(f"Type Error: Unknown binary operator '{node.op}'.")

    def visit_UnaryExpr(self, node: UnaryExpr) -> str:
        op_type = self.get_expr_type(node.operand)
        if node.op == '!':
            if op_type != "bool": 
                raise Exception("Type Error: Logical '!' requires a bool operand.")
            return "bool"
        if node.op in ('-', '~'):
            if op_type != "int": 
                raise Exception(f"Type Error: Mathematical/Bitwise '{node.op}' requires an int operand.")
            return "int"
        raise Exception(f"Type Error: Unknown unary operator '{node.op}'.")

    def visit_TernaryExpr(self, node: TernaryExpr) -> str:
        cond_type = self.get_expr_type(node.condition)
        if cond_type != "bool":
            raise Exception("Type Error: Ternary condition must evaluate to a bool.")
            
        t_type = self.get_expr_type(node.true_expr)
        f_type = self.get_expr_type(node.false_expr)
        
        # Null bubbling
        if t_type == "null": return f_type
        if f_type == "null": return t_type
        
        if t_type != f_type:
            raise Exception(f"Type Error: Ternary branches must match in type. Got {t_type} vs {f_type}.")
            
        return t_type

    def visit_Quantifier(self, node: Quantifier) -> str:
        """Quantifiers introduce a temporary bound variable to the environment."""
        self.env.push_scope()
        self.env.register_var(node.bound_var, node.var_type)
        
        inner_type = self.get_expr_type(node.formula)
        if inner_type != "bool":
            raise Exception("Type Error: Quantifier body formula must evaluate to a bool.")
            
        self.env.pop_scope()
        return "bool"
    
    # ==========================================
    # --- PART 3: Memory & Control Flow ---
    # ==========================================

    def visit_FieldAccess(self, node: FieldAccess) -> str:
        obj_type = self.get_expr_type(node.obj)
        
        # Special rule for sequence length
        if obj_type.startswith("seq[") and node.field == "length":
            return "int"
            
        fields = self.env.get_struct_fields(obj_type)
        if node.field not in fields:
            raise Exception(f"Type Error: Struct '{obj_type}' has no field '{node.field}'.")
            
        return fields[node.field]

    def visit_SeqAccess(self, node: SeqAccess) -> str:
        seq_type = self.get_expr_type(node.seq_obj)
        if not seq_type.startswith("seq["):
            raise Exception(f"Type Error: Cannot index into non-sequence type '{seq_type}'.")
            
        idx_type = self.get_expr_type(node.index)
        if idx_type != "int":
            raise Exception(f"Type Error: Sequence index must be an integer. Got '{idx_type}'.")
            
        # Extract the inner type (e.g., 'seq[int]' -> 'int')
        return seq_type[4:-1]

    def visit_StructUpdate(self, node: StructUpdate) -> str:
        obj_type = self.get_expr_type(node.obj)
        fields = self.env.get_struct_fields(obj_type)
        
        if node.field not in fields:
            raise Exception(f"Type Error: Struct '{obj_type}' has no field '{node.field}'.")
            
        new_val_type = self.get_expr_type(node.new_value)
        
        # Null resolution for struct updates
        if new_val_type == "null":
            pass # Null is allowed to overwrite struct fields
        elif new_val_type != fields[node.field]:
            raise Exception(f"Type Error: Cannot update field '{node.field}' of type '{fields[node.field]}' with value of type '{new_val_type}'.")
            
        return obj_type

    def visit_SeqUpdate(self, node: SeqUpdate) -> str:
        seq_type = self.get_expr_type(node.seq_obj)
        if not seq_type.startswith("seq["):
            raise Exception(f"Type Error: Cannot update non-sequence type '{seq_type}'.")
            
        idx_type = self.get_expr_type(node.index)
        if idx_type != "int":
            raise Exception("Type Error: Sequence index must be an integer.")
            
        inner_type = seq_type[4:-1]
        new_val_type = self.get_expr_type(node.new_value)
        
        if new_val_type != "null" and new_val_type != inner_type:
            raise Exception(f"Type Error: Cannot update sequence of '{inner_type}' with '{new_val_type}'.")
            
        return seq_type

    def visit_FuncCall(self, node: FuncCall) -> str:
        # 1. Is it a Struct Constructor? (e.g., mk_BST)
        if node.name.startswith("mk_") and node.name[3:] in self.env.structs:
            struct_name = node.name[3:]
            fields = list(self.env.get_struct_fields(struct_name).values())
            
            if len(node.args) != len(fields):
                raise Exception(f"Type Error: Constructor '{node.name}' expects {len(fields)} arguments, got {len(node.args)}.")
                
            for i, arg in enumerate(node.args):
                arg_type = self.get_expr_type(arg)
                if arg_type != "null" and arg_type != fields[i]:
                    raise Exception(f"Type Error: Constructor argument {i+1} must be '{fields[i]}'. Got '{arg_type}'.")
            return struct_name

        # 2. It is an Oracle Call
        oracle_def = self.env.get_oracles(node.name)
        if len(node.args) != len(oracle_def.args):
            raise Exception(f"Type Error: Oracle '{node.name}' expects {len(oracle_def.args)} arguments, got {len(node.args)}.")
            
        for i, arg in enumerate(node.args):
            arg_type = self.get_expr_type(arg)
            expected_type = oracle_def.args[i].typeName
            if arg_type != "null" and arg_type != expected_type:
                raise Exception(f"Type Error: Oracle argument {i+1} expects '{expected_type}', got '{arg_type}'.")
                
        return oracle_def.retType

    # --- Statements ---

    def visit_AssignStmt(self, node: AssignStmt) -> None:
        # Strip SSA suffix if present
        base_name = node.lvalue.name.rsplit('_', 1)[0] if ('_' in node.lvalue.name and node.lvalue.name.rsplit('_', 1)[1].isdigit()) else node.lvalue.name
        
        lval_type = self.env.get_var_type(base_name)
        if lval_type is None:
            raise Exception(f"Type Error: Cannot assign to undeclared variable '{base_name}'.")
            
        expr_type = self.get_expr_type(node.expr)
        
        if expr_type != "null" and lval_type != expr_type:
            raise Exception(f"Type Error: Cannot assign type '{expr_type}' to variable '{base_name}' of type '{lval_type}'.")

    def visit_AssumesClause(self, node: AssumesClause) -> None:
        if self.get_expr_type(node.formula) != "bool":
            raise Exception("Type Error: Oracle 'assumes' clause must evaluate to a bool.")
    
    def visit_Returns(self, node: Returns) -> None:
        if self.get_expr_type(node.formula) != "bool":
            raise Exception("Type Error: Returns clauses must evaluate to a boolean equality constraint.")
            
        # Ensure the returns clause actually references the return variable
        # (This is a simplified check; a full check would ensure the equality binds the retName)
        if self.current_func_ret_type is None:
            raise Exception("Type Error: Returns clause found outside of a function.")

    def visit_AssertStmt(self, node: AssertStmt) -> None:
        if self.get_expr_type(node.formula) != "bool":
            raise Exception("Type Error: Assertions must evaluate to a bool.")
        
    def visit_AssumeStmt(self, node: AssumeStmt) -> None:
        if self.get_expr_type(node.formula) != "bool":
            raise Exception("Type Error: Procedural 'assume' statement must evaluate to a bool.")

    def visit_BlockStmt(self, node: BlockStmt) -> None:
        for stmt in node.statements:
            stmt.accept(self)

    def visit_IfStmt(self, node: IfStmt) -> None:
        if self.get_expr_type(node.condition) != "bool":
            raise Exception("Type Error: If condition must evaluate to a bool.")
        node.then_block.accept(self)
        if node.else_block:
            node.else_block.accept(self)

    def visit_WhileStmt(self, node: WhileStmt) -> None:
        if self.get_expr_type(node.condition) != "bool":
            raise Exception("Type Error: While condition must evaluate to a bool.")
        if node.invariant and self.get_expr_type(node.invariant) != "bool":
            raise Exception("Type Error: Loop invariant must evaluate to a bool.")
        node.body.accept(self)
        
    def visit_CallSiteCheck(self, node: CallSiteCheck) -> None:
        if self.get_expr_type(node.formula) != "bool":
            raise Exception("Type Error: CallSiteCheck must evaluate to a bool.")
            
    def visit_LoopTransition(self, node: LoopTransition) -> None:
        pass # Created by SSA pass after Type Checking, so it can be ignored here