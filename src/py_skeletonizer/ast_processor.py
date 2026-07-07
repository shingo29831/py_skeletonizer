# src/py_skeletonizer/ast_processor.py
"""
Role: PythonソースコードのAST解析を行い、1回のパースでスケルトン化・役割抽出・依存関係抽出を同時実行する。
"""
import ast
from typing import List, Optional, Set, Tuple
from .role_extractor import RoleEntry, extract_roles_from_ast
from .dependency_analyzer import DependencyEntry, extract_dependencies_from_ast

KEEP_IMPLEMENTATION_TAGS = ("@keep", "@ai-full", "@preserve")
ROLE_COMMENT_TAGS = ("Role:", "AI:", "Rule:", "Depends:", "Notice:")


class StubTransformer(ast.NodeTransformer):
    def __init__(self, keep_functions: Optional[Set[str]] = None):
        self.keep_functions = keep_functions or set()
        self.current_class_name: Optional[str] = None
        super().__init__()

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        old_class_name = self.current_class_name
        self.current_class_name = node.name
        self.generic_visit(node)
        self.current_class_name = old_class_name
        return node

    def _has_keep_tag_in_docstring(self, node: ast.AST) -> bool:
        docstring = ast.get_docstring(node)
        if not docstring:
            return False
        return any(tag in docstring for tag in KEEP_IMPLEMENTATION_TAGS)

    def _should_keep_implementation(self, node: ast.AST, func_name: str) -> bool:
        if func_name in self.keep_functions:
            return True
        if self.current_class_name and f"{self.current_class_name}.{func_name}" in self.keep_functions:
            return True
        if self._has_keep_tag_in_docstring(node):
            return True
        return False

    def _process_func_node(self, node: ast.AST, func_name: str) -> ast.AST:
        if self._should_keep_implementation(node, func_name):
            self.generic_visit(node)
            return node

        self.generic_visit(node)
        docstring = ast.get_docstring(node)
        new_body = []

        if docstring:
            new_body.append(ast.Expr(value=ast.Constant(value=docstring)))

        new_body.append(ast.Expr(value=ast.Constant(value=Ellipsis)))
        node.body = new_body
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._process_func_node(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._process_func_node(node, node.name)


def process_code_all_in_one(
    source_code: str,
    rel_file_path: str,
    keep_functions: Optional[Set[str]] = None
) -> Tuple[str, List[RoleEntry], DependencyEntry]:
    try:
        tree = ast.parse(source_code)

        roles = extract_roles_from_ast(tree, rel_file_path, source_code)
        dependency = extract_dependencies_from_ast(tree, rel_file_path)

        transformer = StubTransformer(keep_functions=keep_functions)
        transformed_tree = transformer.visit(tree)
        ast.fix_missing_locations(transformed_tree)
        skeleton_code = ast.unparse(transformed_tree)

        return skeleton_code, roles, dependency
    except SyntaxError as e:
        raise ValueError(f"構文解析に失敗しました。無効なPythonコードです ({rel_file_path}): {e}")


def generate_skeleton_code(source_code: str, keep_functions: Optional[Set[str]] = None) -> str:
    skeleton_code, _, _ = process_code_all_in_one(source_code, "", keep_functions)
    return skeleton_code