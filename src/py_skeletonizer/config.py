# src/py_skeletonizer/config.py
"""
Role: フルコードのまま出力する対象(ファイル、ディレクトリ、関数)の設定情報を保持・検証する。
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Set

@dataclass
class SkeletonConfig:
    # 完全に実装を残す対象のパス(ディレクトリまたはファイル)の絶対パスセット
    full_code_paths: Set[Path] = field(default_factory=set)
    # 実装を残す関数・メソッド名("calculate_score" または "UserService.get_user" 形式)
    keep_functions: Set[str] = field(default_factory=set)

    def is_full_code_path(self, target_path: Path) -> bool:
        """
        対象ファイルが、フルコード指定されたファイル自身、または指定されたフォルダ配下にあるか判定する
        """
        for full_path in self.full_code_paths:
            if target_path == full_path or full_path in target_path.parents:
                return True
        return False