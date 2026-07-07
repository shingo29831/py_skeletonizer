# src/py_skeletonizer/syncer.py
"""
Role: 元のプロジェクトと出力先ディレクトリの差分を比較し、ファイルの生成・更新・削除を同期する。
"""
import os
import shutil
from pathlib import Path
from typing import List, Tuple
from .config import SkeletonConfig
from .ast_processor import generate_skeleton_code

class ProjectSyncer:
    def __init__(self, project_root: Path, output_dir: Path, config: SkeletonConfig):
        self.project_root = project_root
        self.output_dir = output_dir
        self.config = config

    def _is_outdated(self, src_file: Path, dest_file: Path) -> bool:
        if not dest_file.exists():
            return True
        # タイムスタンプ比較: ソースファイルが出力ファイルより新しければ更新対象とする
        return os.path.getmtime(src_file) > os.path.getmtime(dest_file)

    def clean_deleted_files(self, current_target_files: List[Path]) -> int:
        """
        出力先に存在するが、現在のプロジェクトターゲットに存在しない古いファイル・フォルダを削除する
        """
        if not self.output_dir.exists():
            return 0

        valid_dest_files = {
            self.output_dir / f.relative_to(self.project_root) for f in current_target_files
        }
        # project_tree.txtは同期プロセス自身が生成するため保護する
        valid_dest_files.add(self.output_dir / "project_tree.txt")

        deleted_count = 0
        for root, _, files in os.walk(self.output_dir):
            for file in files:
                dest_path = Path(root) / file
                if dest_path not in valid_dest_files:
                    try:
                        dest_path.unlink()
                        deleted_count += 1
                    except OSError as e:
                        raise RuntimeError(f"古いファイルの削除に失敗しました: {dest_path} ({e})")

        # 空になったフォルダをクリーンアップする
        for root, dirs, _ in os.walk(self.output_dir, topdown=False):
            for d in dirs:
                dir_path = Path(root) / d
                try:
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                except OSError:
                    pass

        return deleted_count

    def sync_files(self, target_files: List[Path], force_rebuild: bool = False) -> Tuple[int, int]:
        """
        ファイルを差分処理し、(処理/更新した件数, スキップした件数) を返す
        """
        updated_count = 0
        skipped_count = 0

        for src_file in target_files:
            rel_path = src_file.relative_to(self.project_root)
            dest_file = self.output_dir / rel_path

            if not force_rebuild and not self._is_outdated(src_file, dest_file):
                skipped_count += 1
                continue

            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # 条件1: 指定パスまたはフォルダ配下の場合はフルコードでそのままコピー
            if self.config.is_full_code_path(src_file) or src_file.suffix != ".py":
                shutil.copy2(src_file, dest_file)
                updated_count += 1
                continue

            # 条件2: Pythonファイルかつ一部または全スケルトン化対象
            try:
                with open(src_file, "r", encoding="utf-8") as f:
                    source_code = f.read()

                skeleton_code = generate_skeleton_code(
                    source_code, keep_functions=self.config.keep_functions
                )

                with open(dest_file, "w", encoding="utf-8") as f:
                    f.write(skeleton_code)
                
                # 次回の差分検知のためにタイムスタンプを同期
                shutil.copystat(src_file, dest_file)
                updated_count += 1
            except Exception as e:
                # エラー握り潰し禁止のポリシーに従い、例外をラップして通知
                raise RuntimeError(f"ファイル処理中にエラーが発生しました: {src_file} ({e})")

        return updated_count, skipped_count