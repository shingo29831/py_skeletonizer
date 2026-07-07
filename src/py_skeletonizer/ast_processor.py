# src/py_skeletonizer/ast_processor.py
"""
Role: PythonソースコードのAST解析を行い、コメント規則(タグ)に従って保護・スケルトン化を行う。
"""
import ast
from typing import Optional, Set

# 関数全体の中身(実装)を保護して残すための特殊なコメント規則タグ
KEEP_IMPLEMENTATION_TAGS = ("@keep", "@ai-full", "@preserve")

# 役割として認識し、関数をスケルトン化しても Docstring として絶対に削除しないタグ
ROLE_COMMENT_TAGS = ("Role:", "AI:", "Rule:", "Depends:", "Notice:")


class StubTransformer(ast.NodeTransformer):
    """
    ASTを巡回し、ホワイトリストおよびコメントの規則(タグ)に基づいて実装やコメントを保護する
    """
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
        """
        Docstringの中に @keep などの実装保護タグが含まれているか検証する
        """
        docstring = ast.get_docstring(node)
        if not docstring:
            return False
        return any(tag in docstring for tag in KEEP_IMPLEMENTATION_TAGS)

    def _should_keep_implementation(self, node: ast.AST, func_name: str) -> bool:
        """
        CLI引数での指定、またはコメントの規則によるタグ指定のいずれかで保護対象か判定する
        """
        # 1. CLIの --keep-func で指定されている場合
        if func_name in self.keep_functions:
            return True
        if self.current_class_name and f"{self.current_class_name}.{func_name}" in self.keep_functions:
            return True
            
        # 2. コメントの規則: Docstring内に "@keep" や "@ai-full" のタグがある場合
        if self._has_keep_tag_in_docstring(node):
            return True

        return False

    def _process_func_node(self, node: ast.AST, func_name: str) -> ast.AST:
        # 条件1: 関数全体の保護規則に合致する場合は、実装を何も消さずに維持する
        if self._should_keep_implementation(node, func_name):
            self.generic_visit(node)
            return node

        self.generic_visit(node)
        docstring = ast.get_docstring(node)
        new_body = []

        # 条件2: Docstring(役割コメント)が存在する場合の規則チェック
        if docstring:
            # Role: や AI: などの特定のタグで始まっている、または含まれる場合は確実に保持する
            # (ポリシーに則り、今回は一般的なDocstringも含めてセーフティに保持しますが、
            #  もし ROLE_COMMENT_TAGS が含まれるもの「だけ」を残したい場合はここで if 分岐が可能です)
            new_body.append(ast.Expr(value=ast.Constant(value=docstring)))

        # 実装コードは ... (Ellipsis) に置き換え
        new_body.append(ast.Expr(value=ast.Constant(value=Ellipsis)))
        node.body = new_body
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._process_func_node(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._process_func_node(node, node.name)


def generate_skeleton_code(source_code: str, keep_functions: Optional[Set[str]] = None) -> str:
    """
    ソースコードと保護対象の関数名セットを受け取り、コメントの規則を考慮して変換したコードを返す
    """
    try:
        tree = ast.parse(source_code)
        transformer = StubTransformer(keep_functions=keep_functions)
        transformed_tree = transformer.visit(tree)
        ast.fix_missing_locations(transformed_tree)
        return ast.unparse(transformed_tree)
    except SyntaxError as e:
        raise ValueError(f"構文解析に失敗しました。無効なPythonコードです: {e}")