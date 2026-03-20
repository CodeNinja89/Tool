from typing import Dict, List
from core.toolAst import *

class TypeEnvironment:
    def __init__(self):
        self.variables: Dict[str, str] = {}
        self.structs: Dict[str, Dict[str, str]] = {} # Maps struct names to their field layouts (e.g., {"Node": {"value": "uint32", "next": "Node"}})
        self.oracles: Dict[str, FunctionDef] = {}

    def build(self, declarations: List[ASTNode]):
        for decl in declarations:
            if isinstance(decl, VarDecl):
                self.variables[decl.name] = decl.typeName
            elif isinstance(decl, StructDef):
                self.structs[decl.name] = decl.fields
            elif isinstance(decl, FunctionDef):
                self.oracles[decl.name] = decl

    def get_var_type(self, var_name: str) -> str:
        if var_name not in self.variables:
            raise Exception(f"Variable {var_name} is not defined")
        return self.variables[var_name]
    
    def get_struct_fields(self, struct_name: str) -> Dict[str, str]:
        if struct_name not in self.structs:
            raise Exception(f"Struct {struct_name} not defined")
        return self.structs[struct_name]
    
    def get_oracles(self, oracle_name: str) -> FunctionDef:
        if oracle_name not in self.oracles:
            raise Exception(f"Oracle {oracle_name} is not defined")
        return self.oracles[oracle_name]