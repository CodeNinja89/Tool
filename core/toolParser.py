from lark import Lark, Transformer, v_args
from core.toolAst import *

class ToolASTBuilder(Transformer):
    """
    Transforms the LARK parse tree directly into the Object-Oriented AST.
    This class performs NO semantic checking. It only builds data structures.
    """

    def start(self, items):
        return items[0]

    def structured_program(self, items):
        return Program(
            declarations = items[0] if items[0] else [],
            preconditions = items[1] if items[1] else [],
            postconditions = items[2] if items[2] else [],
            specProgram = items[3] if items[3] else []
        )
    
    # --- Sections ---
    def declarations_section(self, items): return items
    def preconditions_section(self, items): return items
    def postconditions_section(self, items): return items
    def program_section(self, items): return items
    
    # --- Declarations ---
    def var_decl(self, items):
        return VarDecl(name=str(items[0]), typeName=str(items[1]), is_refer=False)
        
    def const_decl(self, items):
        # Constants are treated structurally as variables here. 
        # The TypeChecker visitor will enforce their immutability later.
        return VarDecl(name=str(items[0]), typeName=str(items[1]), is_refer=False)
    
    def struct_def(self, items):
        is_linear = items[0] is not None
        struct_name = str(items[1])
        
        fields = {}
        for i in range(2, len(items), 2):
            fields[str(items[i])] = str(items[i + 1])
            
        return StructDef(name=struct_name, fields=fields, is_linear=is_linear)
    
    def invisible_decl(self, items):
        return InvisibleDecl(name=str(items[1]), typeName=str(items[2]))
    
    # --- Types ---
    def base_type(self, items): return str(items[0])
    def user_type(self, items): return str(items[0])
    def seq_type(self, items): return f"seq[{items[0]}]"
    
    # --- Function Definitions (Oracles) ---
    def function_def(self, items):
        name = str(items[0])
        args = items[1] if items[1] is not None else []
        retName = str(items[2])
        retType = str(items[3])
        clauses = items[4] if items[4] else []

        return FunctionDef(name, args, retName, retType, clauses)
    
    def arg_list(self, items): return items
    
    def arg(self, items):
        is_refer = items[0] is not None
        return VarDecl(name=str(items[1]), typeName=str(items[2]), is_refer=is_refer)
    
    def function_body(self, items): return items
    
    def func_assumes(self, items): 
        return AssumesClause(formula=items[0])
    
    def func_returns(self, items): return Returns(formula=items[0])

    # --- Formulas & Mathematical Operators ---
    
    def eq(self, items): return BinaryExpr(items[0], '==', items[1])
    def neq(self, items): return BinaryExpr(items[0], '!=', items[1])
    def lt(self, items): return BinaryExpr(items[0], '<', items[1])
    def lte(self, items): return BinaryExpr(items[0], '<=', items[1])
    def gt(self, items): return BinaryExpr(items[0], '>', items[1])
    def gte(self, items): return BinaryExpr(items[0], '>=', items[1])

    def add(self, items): return BinaryExpr(items[0], '+', items[1])
    def sub(self, items): return BinaryExpr(items[0], '-', items[1])
    def mul(self, items): return BinaryExpr(items[0], '*', items[1])
    def div(self, items): return BinaryExpr(items[0], '/', items[1])
    def mod(self, items): return BinaryExpr(items[0], '%', items[1])

    def logic_and_op(self, items): return BinaryExpr(items[0], '&&', items[1])
    def logic_or_op(self, items): return BinaryExpr(items[0], '||', items[1])
    def not_f(self, items): return UnaryExpr('!', items[0])
    def neg(self, items): return UnaryExpr('-', items[0])

    def bit_or_op(self, items): return BinaryExpr(items[0], '|', items[1])
    def bit_xor_op(self, items): return BinaryExpr(items[0], '^', items[1])
    def bit_and_op(self, items): return BinaryExpr(items[0], '&', items[1])
    def shl(self, items): return BinaryExpr(items[0], '<<', items[1])
    def shr(self, items): return BinaryExpr(items[0], '>>', items[1])
    def bit_not(self, items): return UnaryExpr('~', items[0])

    def ite_expr(self, items):
        return TernaryExpr(condition=items[0], true_expr=items[1], false_expr=items[2])
    
    def forall_f(self, items):
        return Quantifier("forall", str(items[0]), str(items[1]), items[2])
    
    def exists_f(self, items):
        return Quantifier("exists", str(items[0]), str(items[1]), items[2])

    # --- Base Values & Memory Access ---
    
    def number(self, items): return Literal(value=str(items[0]))
    def true_lit(self, items): return Literal("true")
    def false_lit(self, items): return Literal("false")
    def null_lit(self, items): return Literal("null")

    def lvalue(self, items):
        """Translates chained variable, array, and struct field accesses."""
        current_expr = VarRef(str(items[0]))

        for modifier in items[1:]:
            # If the modifier was parsed as an expression, it is a sequence index (e.g., [i])
            if isinstance(modifier, Expr):
                current_expr = SeqAccess(seq_obj=current_expr, index=modifier)
            # Otherwise, it is a struct field access (e.g., .left)
            else:
                current_expr = FieldAccess(obj=current_expr, field=str(modifier))
                
        return current_expr
    
    def func_call(self, items):
        name = str(items[0])
        args = items[1] if len(items) > 1 and items[1] is not None else []
        return FuncCall(name=name, args=args)
    
    def expr_list(self, items): return items
    
    # --- Imperative Statements ---
    
    def assign_stmt(self, items):
        return AssignStmt(lvalue=items[0], expr=items[1])
    
    def assume_stmt(self, items):
        return AssumeStmt(formula=items[0])
    
    def assert_stmt(self, items):
        return AssertStmt(formula=items[0])
    
    def block_stmt(self, items):
        return BlockStmt(statements=items)
    
    def if_stmt(self, items):
        condition = items[0]
        then_block = items[1]
        else_block = items[2] if len(items) > 2 else None
        return IfStmt(condition=condition, then_block=then_block, else_block=else_block)
    
    def while_stmt(self, items):
        """Simplified While statement logic relying strictly on Hoare invariants."""
        condition = items[0]
        body = items[-1]
        # Because we removed 'measure' from the grammar, the items list is either 
        # length 2 (condition, body) or length 3 (condition, invariant, body).
        invariant = items[1] if len(items) == 3 else None
        
        return WhileStmt(condition=condition, invariant=invariant, body=body)