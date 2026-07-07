"""
Role: CLIのエントリーポイント。コマンドライン引数の解析、設定の構築、エラーハンドリングを担当し、ビジネスロジックは他モジュールに委譲する。
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional, Set

from .config import SkeletonConfig
from .scanner import get_target_files, generate_tree_text
from .syncer import ProjectSyncer


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    コマンドライン引数を定義・解析する
    """
    parser = argparse.ArgumentParser(
        prog="py-skeletonizer",
        description="PythonプロジェクトのAST解析を行い、AIコンテキスト向けの軽量スケルトンコピーを生成します。",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # 必須のユーザー入力（第1位置引数）
    parser.add_argument(
        "project_dir",
        type=Path,
        help="解析対象のプロジェクト・ルートディレクトリのパス",
    )

    # 省略可能に変更（第2位置引数、指定がなければNone）
    parser.add_argument(
        "output_dir",
        type=Path,
        nargs="?",
        default=None,
        help="スケルトン化したファイルを出力する先のパス（省略時は '元のプロジェクト名_ai_context' を自動生成）",
    )

    # オプション引数（複数回の指定やカンマ区切りをサポート）
    parser.add_argument(
        "-f", "--full-path",
        action="append",
        default=[],
        help="スケルトン化せずフルコードのまま保持するファイルまたはフォルダのパス。\n複数指定可能（例: -f services/ -f models/user.py）",
    )
    parser.add_argument(
        "-k", "--keep-func",
        action="append",
        default=[],
        help="内部実装（中身）を削除せず保持する関数やメソッド名。\n複数指定可能（例: -k calculate_score -k UserService.get_user）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="タイムスタンプによる差分チェックを無視し、全ファイルを強制的に再処理する",
    )

    return parser.parse_args(args)


def _process_comma_separated_args(arg_list: List[str]) -> Set[str]:
    """
    複数指定およびカンマ区切りで渡された引数リストをフラットなSetに展開する
    """
    result = set()
    for item in arg_list:
        for part in item.split(","):
            cleaned = part.strip()
            if cleaned:
                result.add(cleaned)
    return result


def _resolve_output_dir(project_root: Path, custom_output_dir: Optional[Path]) -> Path:
    """
    出力先ディレクトリのパスを解決する。省略時は元のプロジェクト名に '_ai_context' を付与したパスを返す。
    """
    if custom_output_dir is not None:
        return custom_output_dir.resolve()
    
    # 元のディレクトリ名の末尾に '_ai_context' を追加して自動生成
    default_name = f"{project_root.name}_ai_context"
    return project_root.with_name(default_name)


def main(args: Optional[List[str]] = None) -> int:
    """
    CLI全体の実行フローを制御するメインハンドラ。終了コードを返す。
    """
    try:
        parsed_args = parse_arguments(args)

        project_root: Path = parsed_args.project_dir.resolve()

        # 入力値の検証（エラー握り潰し厳禁）
        if not project_root.exists() or not project_root.is_dir():
            print(f"エラー: 指定されたソースディレクトリが存在しません: {project_root}", file=sys.stderr)
            return 1

        # 出力先パスの決定（省略時の自動解決ロジックを適用）
        output_dir: Path = _resolve_output_dir(project_root, parsed_args.output_dir)

        if project_root == output_dir:
            print("エラー: ソースディレクトリと出力先ディレクトリに同じパスは指定できません。", file=sys.stderr)
            return 1

        # フルパス指定の解決（プロジェクトルートからの相対パスおよび絶対パスを考慮）
        raw_full_paths = _process_comma_separated_args(parsed_args.full_path)
        resolved_full_paths: Set[Path] = set()
        for path_str in raw_full_paths:
            p = Path(path_str)
            if not p.is_absolute():
                p = (project_root / p).resolve()
            resolved_full_paths.add(p)

        # 関数のホワイトリスト展開
        keep_functions = _process_comma_separated_args(parsed_args.keep_func)

        # 設定情報の構築
        config = SkeletonConfig(
            full_code_paths=resolved_full_paths,
            keep_functions=keep_functions,
        )

        print(f"解析を開始します: {project_root}")
        if parsed_args.output_dir is None:
            print(f"  - 出力先を自動設定しました: {output_dir.name}")
        if config.full_code_paths:
            print(f"  - フルコード保持パス: {len(config.full_code_paths)}件")
        if config.keep_functions:
            print(f"  - 保持対象関数・メソッド: {', '.join(config.keep_functions)}")
        if parsed_args.force:
            print("  - 強制再ビルドモード(--force)が有効です")

        # 1. 処理対象のファイルリスト取得 (.gitignoreパターンの適用)
        target_files = get_target_files(project_root)

        # 2. 差分同期エンジンの実行
        syncer = ProjectSyncer(project_root, output_dir, config)
        
        # 削除された古いファイルのクリーンアップ
        deleted_count = syncer.clean_deleted_files(target_files)
        
        # ファイルの同期（作成・更新・スキップ）
        updated_count, skipped_count = syncer.sync_files(
            target_files, force_rebuild=parsed_args.force
        )

        # 3. AI向けプロジェクトツリー出力の生成
        tree_text = generate_tree_text(project_root, target_files)
        tree_file = output_dir / "project_tree.txt"
        with open(tree_file, "w", encoding="utf-8") as f:
            f.write("=== AI Context Project Structure ===\n")
            f.write(tree_text)

        # 実行結果のフィードバック
        print("\n=== 同期完了 ===")
        print(f"出力先ディレクトリ: {output_dir}")
        print(f"  - 更新/処理ファイル数 : {updated_count} 件")
        print(f"  - 変更なし(スキップ)   : {skipped_count} 件")
        if deleted_count > 0:
            print(f"  - 削除した古いファイル: {deleted_count} 件")
        print(f"  - ツリー構造マップ     : project_tree.txt に出力しました")

        return 0

    except Exception as e:
        # 例外を握り潰さず、エラー内容をスタックトレースと共に分かりやすく通知
        print(f"\n致命的なエラーが発生しました: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())