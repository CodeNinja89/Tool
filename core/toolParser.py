from lark import Lark, Transformer, v_args
from core.toolAst import *

class CHCTransformer(Transformer):

    def start(self, items):
        # items[0] is the result of structured_program
        return items[0]

    def structured_program(self, items):
        return Program(
            declarations = items[0],
            preconditions = items[1],
            postconditions = items[2],
            specProgram = items[3]
        )
    
    # --- Sections ---
    
    def declarations_section(self, items):
        return items
    def preconditions_section(self, items):
        return items
    def postconditions_section(self, items):
        return items
    def program_section(self, items):
        return items
    
    # --- Declarations ---
    
    def var_decl(self, items):
        name = str(items[0])
        typeName = str(items[1])
        return VarDecl(name, typeName)
    
    def struct_def(self, items):
        struct_name = str(items[0])
        fields = {}

        for i in range(1, len(items), 2):
            field_name = str(items[i])
            field_type = str(items[i + 1])
            fields[field_name] = field_type
        
        return StructDef(struct_name, fields)
    
    # --- Types ---
    
    def base_type(self, items):
        return str(items[0])
    
    def user_type(self, items):
        return str(items[0])
    
    def seq_type(self, items):
        return f"seq[{items[0]}]" # Simple string representation for now
    
    # --- Function Definitions ---
    
    def function_def(self, items):
        # Grammar: "oracle" NAME "(" [arg_list] ")" "->" NAME ":" type "{" function_body "}"
        # [name, arg_list_opt, ret_name, ret_type, body]

        name = str(items[0])
        args = items[1] if items[1] is not None else []
        retName = str(items[2])
        retType = str(items[3])
        clauses = items[4]

        return FunctionDef(name, args, retName, retType, clauses)
    
    def arg_list(self, items):
        return items
    
    def arg(self, items):
        return VarDecl(str(items[0]), str(items[1]))
    
    def function_body(self, items):
        return items
    
    # --- Clauses --

    def func_assumes(self, items):
        return Assume(formula=items[0])
    
    def func_returns(self, items):
        return Returns(formula=items[0])
        
    # --- Formulas (Simple String Pass-through) ---
    # We will convert logic to strings temporarily to test the AST structure
    
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

    def ite_expr(self, items):
        return TernaryExpr(condition = items[0], true_expr=items[1], false_expr=items[2])
    
    def forall_f(self, items):
        bound_var = str(items[0])
        var_type = str(items[1])
        inner_expr = items[2]
        return Quantifier(
            quant_type="forall",
            bound_var=bound_var,
            var_type=var_type,
            formula=inner_expr
        )
    
    def exists_f(self, items):
        bound_var = str(items[0])
        var_type = str(items[1])
        inner_expr = items[2]
        return Quantifier(
            quant_type="exists",
            bound_var=bound_var,
            var_type=var_type,
            formula=inner_expr
        )

    def bit_or_op(self, items): return BinaryExpr(items[0], '|', items[1])
    def bit_xor_op(self, items): return BinaryExpr(items[0], '^', items[1])
    def bit_and_op(self, items): return BinaryExpr(items[0], '&', items[1])
    def shl(self, items): return BinaryExpr(items[0], '<<', items[1])
    def shr(self, items): return BinaryExpr(items[0], '>>', items[1])
    def bit_not(self, items): return UnaryExpr('~', items[0])

    # base of the tree
    def number(self, items):
        return Literal(value=str(items[0]))
    
    def true_lit(self, items):
        return Literal("true")
    def false_lit(self, items):
        return Literal("false")
    def lvalue(self, items):
        base_expr = VarRef(str(items[0]))

        if len(items) == 1:
            return base_expr # this is a normal variable
        
        # else we have a chain of accesses
        current_expr = base_expr
        for modifier in items[1:]:
            if isinstance(modifier, Expr):
                # it's a sequence index
                current_expr = SeqAccess(seq_obj=current_expr, index=modifier)
            else:
                current_expr = FieldAccess(obj=current_expr, field=str(modifier))
        return current_expr
    
    def func_call(self, items):
        name = str(items[0])
        args = items[1] if len(items) > 1 and items[1] is not None else []
        return FuncCall(name, args)
    
    def expr_list(self, items):
        return items
    
    def assign_stmt(self, items):
        return AssignStmt(items[0], items[1])
    
    def assert_stmt(self, items):
        return AssertStmt(items[0])
    
    def block_stmt(self, items):
        return BlockStmt(items)
    
    def if_stmt(self, items):
        condition = items[0]
        then_block = items[1]
        else_block = items[2] if len(items) > 2 else None
        return IfStmt(condition, then_block, else_block)
    
    def while_stmt(self, items):
        condition = items[0]
        body = items[-1]
        invariant = None
        measure = None

        if len(items) == 3:
            invariant = items[1]
        elif len(items) == 4:
            invariant = items[1]
            measure = items[2]

        return WhileStmt(condition, invariant, measure, body)
