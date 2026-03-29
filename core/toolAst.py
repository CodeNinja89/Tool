# holds all the semantic information

from dataclasses import dataclass
from typing import List, Optional, Union, Dict

@dataclass
class ASTNode:
    pass

@dataclass
class Program(ASTNode):
    declarations: List[ASTNode]
    preconditions: List[ASTNode]
    postconditions: List[ASTNode]
    specProgram: List[ASTNode]

@dataclass
class VarDecl(ASTNode):
    name: str
    typeName: str

@dataclass
class StructDef(ASTNode):
    name: str # name of the struct
    fields: Dict[str, str] # fields of a struct

@dataclass
class FunctionDef(ASTNode):
    name: str
    args: List[VarDecl]
    retName: str
    retType: str
    clauses: List[ASTNode]

@dataclass
class Expr(ASTNode):
    pass

@dataclass
class BinaryExpr(Expr):
    left: Expr
    op: str
    right: Expr

@dataclass
class TernaryExpr(Expr):
    condition: Expr
    true_expr: Expr
    false_expr: Expr

@dataclass
class UnaryExpr(Expr):
    op: str
    operand: Expr

@dataclass
class Quantifier(Expr):
    quant_type: str
    bound_var: str
    var_type: str
    formula: Expr

@dataclass
class VarRef(Expr):
    name: str

@dataclass
class Literal(Expr):
    value: str

@dataclass
class FuncCall(Expr):
    name: str
    args: List[Expr]

@dataclass
class FieldAccess(Expr):
    # access the field of a struct
    obj: Expr
    field: str

@dataclass
class SeqAccess(Expr):
    # access a specific index in a sequence
    seq_obj: Expr
    index: Expr

@dataclass
class StructUpdate(Expr):
    # turn a field assignement into a SSA
    obj: Expr
    field: str
    new_value: Expr

@dataclass
class SeqUpdate(Expr):
    seq_obj: Expr
    index: Expr
    new_value: Expr

@dataclass
class LoopTransition(Expr):
    pre_loop_scope: Dict[str, int] # timeline before the loop starts
    read_scope: Dict[str, int]     # timeline at the start of the arbitrary i-th iteration
    write_scope: Dict[str, int]    # timeline at the end of the i-th iteration
    
    inv_pre: Expr                  # invariant evaluated BEFORE the loop (Base Case)
    inv_read: Expr                 # invariant evaluated at start of loop (Inductive Assumption)
    inv_write: Expr                # invariant evaluated at end of loop (Inductive Proof)
    
    cond_read: Expr                # loop condition evaluated at start of loop
    
    measure_read: Optional[Expr]   # measure evaluated at start of loop
    measure_write: Optional[Expr]  # measure evaluated at end of loop
    
    body_formulas: List[Expr]      # the mutated state transitions inside the loop

@dataclass
class CallSiteCheck:
    formula: 'Expr'

@dataclass
class Assume(ASTNode):
    formula: Expr

@dataclass
class Returns(ASTNode):
    formula: Expr

@dataclass
class Stmt(ASTNode):
    pass

@dataclass
class AssignStmt(Stmt):
    lvalue: VarRef
    expr: Expr

@dataclass
class AssertStmt(Stmt):
    formula: Expr

@dataclass
class BlockStmt(Stmt):
    statements: List[Stmt]

@dataclass
class IfStmt(Stmt):
    condition: Expr
    then_block: BlockStmt
    else_block: Optional[BlockStmt]

@dataclass
class WhileStmt(Stmt):
    condition: Expr
    invariant: Optional[Expr]
    measure: Optional[Expr]
    body: BlockStmt
