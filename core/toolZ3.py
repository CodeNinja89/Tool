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