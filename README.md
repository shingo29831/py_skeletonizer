py-skeletonizer

py-skeletonizer は、Pythonプロジェクトのコードベースを抽象構文木（AST）レベルで解析し、AI（LLM）へのインプットに最適化された軽量なコンテキストコピー、役割マップ、依存関係グラフ、および単一ファイルへの統合バンドルを自動生成・同期するCLIツールです。

関数やクラスのシグネチャ、Docstring、ファイル冒頭の役割記述（Role）のみを残して内部ロジックを省略（スケルトン化）することで、AIにプロジェクト全体の構造を正確に伝えつつ、消費トークン量を大幅に削減（最大70〜90%以上削減）します。

📦 インストールと環境構築 (Installation)

1. 依存モジュールのインストール

プロジェクトを実行するために必要な依存ライブラリを requirements.txt からインストールします。

# コア依存および開発・テスト用ライブラリの一括インストール
pip install -r requirements.txt


2. どこからでも使えるようにする（グローバルコマンド化）

本ツールは pyproject.toml にエイリアスが定義されており、以下のコマンドでインストールすることで、システムのどのパス（ディレクトリ）からでも py-skeletonizer または pyskel というコマンド名で直接実行できるようになります。

# カレントディレクトリのパッケージを環境にインストール（どこからでも実行可能になります）
pip install .

# 開発者向け：コードの変更をリアルタイムに反映させる場合の編集可能モードインストール
pip install -e .


🚀 使い方とオプション詳細 (Usage & Options)

環境へのインストールが完了すると、以下の構文で任意のPythonプロジェクトを解析できます。

py-skeletonizer <解析対象プロジェクトのパス> [出力先パス] [オプション]
# または
pyskel <解析対象プロジェクトのパス> [出力先パス] [オプション]


コマンドライン引数・オプション一覧

オプション

短縮形

引数の型

説明

project_dir

(位置引数)

Path

【必須】 解析対象とするPythonプロジェクトのルートディレクトリ。

output_dir

(位置引数)

Path

【任意】 スケルトン群やメタデータを出力するディレクトリ。省略した場合は、自動的に [対象プロジェクト名]_ai_context というフォルダ名で作成されます。

--full-path

-f

str

【複数指定可】 スケルトン化（中身の省略）を行わず、フルコードのまま完全に保持したいファイルやフォルダのパスを指定します。

--keep-func

-k

str

【複数指定可】 内部ロジックを削除せず保持したい特定の関数名やメソッド名を指定します。カンマ区切りでの複数指定も可能です。

--no-bundle

-

なし

単一統合バンドルファイル（ai_context_bundle.*）の書き出しをスキップします。

--format

-

xml | markdown

統合バンドルファイルの出力フォーマットを指定します（デフォルト: xml）。ブラウザAIへのコピペにはXMLが推奨されます。

--policy

-

Path

バンドルファイルの冒頭に自動注入するカスタムポリシー（開発ルールなど）のファイルを指定します。省略時は自動探索されます。

--force

-

なし

タイムスタンプによるファイルの差分チェックを無視し、全ファイルを強制的に再解析・再処理します。

💡 実行例 (Examples)

1. 最もシンプルな実行（出力先自動生成）

py-skeletonizer ./my_project


./my_project_ai_context/ が自動生成され、その中の ai_meta/ フォルダに統合バンドルや各種マップが集約されます。

2. 詳細なオプションを指定した高度な実行

py-skeletonizer ./my_project ./ai_ready_context \
  -f "src/core/crypto.py" \
  -f "plugins/" \
  -k "validate_token,AuthService.login" \
  --format markdown \
  --policy ./my_rules.md \
  --force


解説: ./my_project を解析し ./ai_ready_context に出力します。暗号化モジュールとプラグインフォルダはフルコードを維持し、validate_token 関数と AuthService.login メソッドの中身は削除せず保護します。また、Markdown形式でバンドルを出力し、独自の開発ルールファイルを注入して強制再生成を行います。

📂 出力成果物の構造

解析が完了すると、指定した出力先に以下の構造でファイルが同期・生成されます。

ai_ready_context/
├── ai_meta/
│   ├── project_tree.txt         # プロジェクト全体のディレクトリ構造マップ
│   ├── project_roles.md         # 各モジュール・クラス・関数の責務集約レポート ✨
│   ├── project_dependencies.md  # 影響範囲を特定するためのインポート依存関係グラフ 🔗
│   └── ai_context_bundle.xml    # AIへのコピペに最適な全コード統合単一バンドル 📦
└── src/                         # 元の構造を維持したまま、中身を省略（...）したPythonコード群


スケルトン化のビフォー・アフター

元のコード (src/auth.py)

# Role: ユーザー認証とトークン制御を担うコアコンポーネント

def login(username, password):
    """ユーザーの認証チェックを行います"""
    if not username or not password:
        return False
    # 複雑なDBクエリやハッシュ計算ロジック（数十行）
    return True


スケルトン化された出力コード

# Role: ユーザー認証とトークン制御を担うコアコンポーネント

def login(username, password):
    """ユーザーの認証チェックを行います"""
    ...


これにより、AIは「どのファイルがどんな役割を持ち、どんな関数が存在するか」という高度なコンテキストを最小限のトークン消費量で把握することができます。