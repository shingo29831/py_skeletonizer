# src/py_skeletonizer/cli.py
"""
Role: CLIのエントリーポイント。コマンドライン引数の解析、設定の構築、エラーハンドリングと結果統計の表示を担当する。
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional, Set

from .config import SkeletonConfig
from .scanner import get_target_files, generate_tree_text
from .syncer import ProjectSyncer


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="py-skeletonizer",
        description="PythonプロジェクトのAST解析を行い、AIコンテキスト向けの軽量スケルトンコピー、役割マップ、依存関係グラフ、単一バンドルを生成します。",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "project_dir",
        type=Path,
        help="解析対象のプロジェクト・ルートディレクトリのパス",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        nargs="?",
        default=None,
        help="スケルトン化したファイルを出力する先のパス（省略時は '元のプロジェクト名_ai_context' を自動生成）",
    )
    parser.add_argument(
        "-f", "--full-path",
        action="append",
        default=[],
        help="スケルトン化せずフルコードのまま保持するファイルまたはフォルダのパス",
    )
    parser.add_argument(
        "-k", "--keep-func",
        action="append",
        default=[],
        help="内部実装（中身）を削除せず保持する関数やメソッド名",
    )
    parser.add_argument(
        "--no-bundle",
        action="store_true",
        help="単一ファイル・バンドル(ai_context_bundle)の出力を行わない",
    )
    parser.add_argument(
        "--format",
        choices=["xml", "markdown"],
        default="xml",
        help="単一バンドルファイルの出力フォーマット (デフォルト: xml)",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="バンドルに自動注入するカスタムポリシーファイルのパス (省略時は自動探索またはデフォルト)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="タイムスタンプによる差分チェックを無視し、全ファイルを強制的に再処理する",
    )

    return parser.parse_args(args)


def _process_comma_separated_args(arg_list: List[str]) -> Set[str]:
    result = set()
    for item in arg_list:
        for part in item.split(","):
            cleaned = part.strip()
            if cleaned:
                result.add(cleaned)
    return result


def _resolve_output_dir(project_root: Path, custom_output_dir: Optional[Path]) -> Path:
    if custom_output_dir is not None:
        return custom_output_dir.resolve()
    default_name = f"{project_root.name}_ai_context"
    return project_root.with_name(default_name)


def main(args: Optional[List[str]] = None) -> int:
    try:
        parsed_args = parse_arguments(args)
        project_root: Path = parsed_args.project_dir.resolve()

        if not project_root.exists() or not project_root.is_dir():
            print(f"エラー: 指定されたソースディレクトリが存在しません: {project_root}", file=sys.stderr)
            return 1

        output_dir: Path = _resolve_output_dir(project_root, parsed_args.output_dir)

        if project_root == output_dir:
            print("エラー: ソースディレクトリと出力先ディレクトリに同じパスは指定できません。", file=sys.stderr)
            return 1

        raw_full_paths = _process_comma_separated_args(parsed_args.full_path)
        resolved_full_paths: Set[Path] = set()
        for path_str in raw_full_paths:
            p = Path(path_str)
            if not p.is_absolute():
                p = (project_root / p).resolve()
            resolved_full_paths.add(p)

        keep_functions = _process_comma_separated_args(parsed_args.keep_func)

        config = SkeletonConfig(
            full_code_paths=resolved_full_paths,
            keep_functions=keep_functions,
            create_bundle=not parsed_args.no_bundle,
            bundle_format=parsed_args.format,
            policy_path=parsed_args.policy.resolve() if parsed_args.policy else None,
        )

        print(f"解析を開始します: {project_root}")
        if parsed_args.output_dir is None:
            print(f"  - 出力先を自動設定しました: {output_dir.name}")
        if config.full_code_paths:
            print(f"  - フルコード保持パス: {len(config.full_code_paths)}件")
        if config.keep_functions:
            print(f"  - 保持対象関数・メソッド: {', '.join(config.keep_functions)}")
        if config.create_bundle:
            print(f"  - バンドル形式: {config.bundle_format.upper()}")
        if parsed_args.force:
            print("  - 強制再ビルドモード(--force)が有効です")

        target_files = get_target_files(project_root)
        tree_text = generate_tree_text(project_root, target_files)

        syncer = ProjectSyncer(project_root, output_dir, config)
        deleted_count = syncer.clean_deleted_files(target_files)
        updated_count, skipped_count, bundle_path = syncer.sync_files(
            target_files, tree_text=tree_text, force_rebuild=parsed_args.force
        )

        tree_file = output_dir / "project_tree.txt"
        tree_file.write_text("=== AI Context Project Structure ===\n" + tree_text, encoding="utf-8")

        stats = syncer.token_stats
        print("\n=== 同期およびコンテキスト最適化完了 ===")
        print(f"出力先ディレクトリ: {output_dir}")
        print(f"  - 更新/処理ファイル数 : {updated_count} 件")
        print(f"  - 変更なし(スキップ)   : {skipped_count} 件")
        if deleted_count > 0:
            print(f"  - 削除した古いファイル: {deleted_count} 件")
        print("\n--- 📊 辞書・マニュアル出力 ---")
        print(f"  - ツリー構造マップ     : project_tree.txt")
        print(f"  - 役割退避マニュアル   : project_roles.md ✨")
        print(f"  - 依存関係グラフ       : project_dependencies.md 🔗")
        if bundle_path:
            print(f"  - 単一統合バンドル     : {bundle_path.name} 📦 (ブラウザAIへそのままコピペ推奨)")

        print("\n--- 📉 トークン・予算削減アナライザー ---")
        print(f"  - 元コード推定トークン : 約 {stats.raw_tokens_est:,} tokens ({stats.raw_chars:,} 文字)")
        print(f"  - 出力コード推定トークン: 約 {stats.skeleton_tokens_est:,} tokens ({stats.skeleton_chars:,} 文字)")
        print(f"  - 削減されたトークン数 : 約 {stats.saved_tokens:,} tokens")
        print(f"  - トークン削減率       : {stats.reduction_percentage:.1f}% 削減の大幅なスリム化に成功！🚀")

        return 0

    except Exception as e:
        print(f"\n致命的なエラーが発生しました: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())