# src/py_skeletonizer/bundle_builder.py
"""
Role: ポリシー、プロジェクトツリー、全体辞書、スケルトンコード群を1つのバンドルファイルに統合し、トークン削減率を計算する。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TokenStats:
    raw_chars: int = 0
    skeleton_chars: int = 0

    @property
    def raw_tokens_est(self) -> int:
        return self.raw_chars // 3

    @property
    def skeleton_tokens_est(self) -> int:
        return self.skeleton_chars // 3

    @property
    def saved_tokens(self) -> int:
        return max(0, self.raw_tokens_est - self.skeleton_tokens_est)

    @property
    def reduction_percentage(self) -> float:
        if self.raw_chars == 0:
            return 0.0
        return (1.0 - (self.skeleton_chars / self.raw_chars)) * 100.0


def _discover_policy_text(project_root: Path, custom_policy_path: Optional[Path]) -> str:
    if custom_policy_path and custom_policy_path.exists():
        try:
            return custom_policy_path.read_text(encoding="utf-8")
        except OSError as e:
            raise RuntimeError(f"指定されたポリシーファイルの読み込みに失敗しました: {custom_policy_path} ({e})")

    candidate_names = [".cursorrules", ".windsurfrules", "AI_POLICY.md", "RULE.md", "CLAUDE.md"]
    for name in candidate_names:
        candidate_path = project_root / name
        if candidate_path.exists():
            try:
                return candidate_path.read_text(encoding="utf-8")
            except OSError:
                continue

    return "・冒頭でファイルの役割を明示。UIとロジックは疎結合に。\n・修正時はファイル内のコードを省略せず出力。\n・エラー握り潰し厳禁、根本解決を。"


def build_bundle_file(
    project_root: Path,
    output_dir: Path,
    tree_text: str,
    role_map_text: str,
    dependency_map_text: str,
    file_contents: Dict[str, str],
    bundle_format: str = "xml",
    custom_policy_path: Optional[Path] = None,
) -> Path:
    policy_text = _discover_policy_text(project_root, custom_policy_path)
    bundle_path = output_dir / f"ai_context_bundle.{bundle_format}"

    lines: List[str] = []

    if bundle_format == "xml":
        lines.append("<ai_context_bundle>")
        lines.append("  <policy>")
        lines.append(policy_text.strip())
        lines.append("  </policy>")
        lines.append("")
        lines.append("  <project_tree>")
        lines.append(tree_text.strip())
        lines.append("  </project_tree>")
        lines.append("")
        lines.append("  <role_architecture_map>")
        lines.append(role_map_text.strip())
        lines.append("  </role_architecture_map>")
        lines.append("")
        lines.append("  <dependency_graph>")
        lines.append(dependency_map_text.strip())
        lines.append("  </dependency_graph>")
        lines.append("")
        lines.append("  <codebase>")
        for rel_path, content in sorted(file_contents.items()):
            lines.append(f'    <file path="{rel_path}">')
            lines.append(content.rstrip())
            lines.append("    </file>")
        lines.append("  </codebase>")
        lines.append("</ai_context_bundle>")
    else:
        lines.append("# AI Context Bundle")
        lines.append("## Policy & Rules")
        lines.append(policy_text.strip())
        lines.append("")
        lines.append("## Project Tree")
        lines.append("```text")
        lines.append(tree_text.strip())
        lines.append("```")
        lines.append("")
        lines.append(role_map_text.strip())
        lines.append("")
        lines.append(dependency_map_text.strip())
        lines.append("")
        lines.append("## Codebase Files")
        for rel_path, content in sorted(file_contents.items()):
            lines.append(f"### File: `{rel_path}`")
            lines.append("```python")
            lines.append(content.rstrip())
            lines.append("```")
            lines.append("")

    try:
        bundle_path.write_text("\n".join(lines), encoding="utf-8")
        return bundle_path
    except OSError as e:
        raise RuntimeError(f"バンドルファイルの生成に失敗しました: {bundle_path} ({e})")