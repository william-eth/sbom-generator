# SBOM Generator

[English Version](README.md)

一個用於生成軟體物料清單（Software Bill of Materials, SBOM）報告的工具。支援從 Lock 檔案和 Dockerfile 中提取所有套件的依賴關係、Repository URL 和 License 資訊。

## 功能特點

- ✅ 支援多種套件管理器（請參閱[支援的語言](#支援的語言)）
- ✅ 自動建立完整的依賴關係圖
- ✅ 從 npm/RubyGems/PyPI registry 查詢 Repository URL
- ✅ 從 GitHub API 取得 License 資訊
- ✅ 驗證 License 內容是否符合標準模板
- ✅ 輸出 UTF-8 with BOM 的 CSV 檔案（Excel 相容）
- ✅ 顯示處理進度
- ✅ 詳細的錯誤報告

## 支援的類型

### 應用程式套件

| 語言 | 套件管理器 | 檔案 | Registry |
|-----|-----------|------|----------|
| JavaScript / Node.js | Yarn | `yarn.lock` | npm Registry |
| Ruby | Bundler | `Gemfile.lock` | RubyGems |
| Python | pip | `requirements.txt` | PyPI |

### OS 系統套件

| OS 類型 | 套件管理器 | 輸入檔案 | 資料來源 |
|--------|-----------|---------|----------|
| Debian / Ubuntu | APT | `Dockerfile` | Debian Sources API / Tracker |

### 計畫支援（未來）

| 類型 | 套件管理器 | 檔案 | 狀態 |
|-----|-----------|-----|------|
| JavaScript / Node.js | npm | `package-lock.json` | 🔜 計畫中 |
| JavaScript / Node.js | pnpm | `pnpm-lock.yaml` | 🔜 計畫中 |
| Python | Poetry | `poetry.lock` | 🔜 計畫中 |
| Python | Pipenv | `Pipfile.lock` | 🔜 計畫中 |
| Python | uv | `uv.lock` | 🔜 計畫中 |
| PHP | Composer | `composer.lock` | 🔜 計畫中 |
| Alpine Linux | APK | `Dockerfile` | 🔜 計畫中 |

## 系統需求

- Python 3.9+
- 網路連線（用於查詢 npm/RubyGems/PyPI registry 和 GitHub API）

## 安裝

```bash
# 1. Clone 或下載此專案
cd sbom-generator

# 2. 建立虛擬環境
python3 -m venv venv

# 3. 啟動虛擬環境
source venv/bin/activate  # macOS/Linux
# 或
.\venv\Scripts\activate   # Windows

# 4. 安裝依賴
pip install -r requirements.txt

# 5. 設定 GitHub Token（建議）
cp config.yaml.example config.yaml
# 編輯 config.yaml，填入您的 GitHub Token
```

## 設定

### GitHub Token（建議設定）

為了避免 API rate limit 限制，建議設定 GitHub Personal Access Token：

| 狀態 | Rate Limit |
|------|-----------|
| 未設定 Token | 60 requests/hour |
| 已設定 Token | 5,000 requests/hour |

**取得 Token 的步驟：**

1. 前往 [GitHub Settings > Tokens](https://github.com/settings/tokens)
2. 點選 "Generate new token (classic)"
3. 選擇 scope: `public_repo`
4. 複製 Token 並填入 `config.yaml`

```yaml
# config.yaml
GITHUB_TOKEN: "your_github_token_here"
LICENSE_SIMILARITY_THRESHOLD: 0.9
```

## 目錄結構

```
sbom-generator/
├── .github/workflows/   # 🔄 GitHub Actions CI/CD
│   └── test.yml         # 測試工作流程
├── input_file/          # 📥 放入您的 lock 檔案或 Dockerfile
│   ├── yarn.lock
│   ├── package.json     # (選用) 用於識別直接依賴
│   ├── Gemfile.lock
│   ├── requirements.txt # Python pip 依賴檔案
│   └── Dockerfile       # Dockerfile (支援 Debian/Ubuntu)
├── output_file/         # 📤 產出的 CSV 報告
│   ├── yarn_sbom_app_yyyymmdd_hhmmss.csv         # 應用程式套件
│   ├── requirements_sbom_app_yyyymmdd_hhmmss.csv # Python 套件
│   └── Dockerfile_sbom_os_yyyymmdd_hhmmss.csv    # OS 系統套件
├── tests/               # 🧪 測試程式碼
│   ├── fixtures/        # 測試用的 fixture 檔案
│   ├── test_models.py   # 資料模型測試
│   ├── test_parsers.py  # 解析器測試
│   └── test_output.py   # CSV 輸出測試
├── config.yaml          # 設定檔（請從 config.yaml.example 複製）
├── config.yaml.example  # 設定檔範例
├── main.py              # 主程式
├── requirements.txt     # Python 依賴（本工具使用）
└── sbom/                # 程式模組
```

### 關於 package.json（選用）

對於 `yarn.lock` 檔案，您可以選擇性地將專案的 `package.json` 放在同一目錄下：

| 有 package.json | 無 package.json |
|-----------------|-----------------|
| ✅ 可識別直接依賴（標示 `[直接依賴]`） | ⚠️ 無法識別直接依賴 |
| ✅ 只會顯示被其他套件引用的資訊 | ✅ 只會顯示被其他套件引用的資訊 |

**建議**：如果需要在報告中區分直接依賴和間接依賴，請將 `package.json` 與 `yarn.lock` 放在同一目錄下。

### 關於 requirements.txt

Python 的 `requirements.txt` 不包含依賴關係資訊，因此：

| 特性 | 說明 |
|------|------|
| 直接依賴 | 檔案中所有套件都標記為 `[直接依賴]` |
| 間接依賴 | 無法識別（requirements.txt 不記錄依賴樹） |
| 版本資訊 | 從版本指定符中提取（如 `>=2.28.0` → `2.28.0`） |

**注意**：如果需要完整的依賴樹分析，建議使用 `poetry.lock` 或 `Pipfile.lock`（未來將支援）。

## 使用方式

### 基本用法

```bash
# 啟動虛擬環境
source venv/bin/activate

# 方法 1: 處理 input_file/ 目錄下的所有檔案
python main.py

# 方法 2: 處理指定的檔案
python main.py input_file/yarn.lock
python main.py input_file/Gemfile.lock
python main.py input_file/requirements.txt
python main.py input_file/Dockerfile

# 方法 3: 處理任意路徑的檔案
python main.py /path/to/your/project/yarn.lock
python main.py /path/to/your/project/requirements.txt
python main.py /path/to/your/project/Dockerfile
```

### 進階選項

```bash
# 指定輸出目錄
python main.py --output ./my_reports

# 指定設定檔
python main.py --config /path/to/config.yaml

# 查看說明
python main.py --help
```

### 快取選項

本工具會快取 API 回應以加速後續執行：

```bash
# 使用快取（預設行為）
python main.py --cache

# 忽略快取，重新取得資料
python main.py --no-cache

# 清除快取並退出
python main.py --clear-cache
```

**快取說明：**
- 快取檔案：`sbom_cache.json`（位於專案根目錄）
- 快取過期時間：7 天
- 首次執行：從 API 取得所有資料
- 後續執行：使用快取資料（速度大幅提升）

## 輸出格式

輸出的 CSV 檔案依類型分為兩種：

### 應用程式套件 (`*_sbom_app_*.csv`)

| 欄位 | 說明 |
|------|------|
| 套件名稱 | Package name |
| 引用套件名稱 | 被哪些套件引用（`[直接依賴]` 表示專案直接使用） |
| 套件 Repo URL | GitHub Repository URL |
| License 名稱 | License 名稱（使用 [GitHub 官方 SPDX ID](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository#searching-github-by-license-type)） |
| License URL | License 檔案的 GitHub 連結 |
| 備註 | 異常說明（非標準 License、非 GitHub 來源、無法取得等） |

### OS 系統套件 (`*_sbom_os_*.csv`)

| 欄位 | 說明 |
|------|------|
| 套件名稱 | Package name |
| 安裝來源 | `[直接依賴]` 表示在 Dockerfile 中明確安裝 |
| 套件 URL | Debian Tracker URL |
| License 名稱 | 從 debian/copyright 解析的 License 列表 |
| License URL | debian/copyright 檔案連結 |
| VCS URL | 版本控制系統 URL（如 Salsa GitLab） |
| 備註 | 其他說明 |

### 範例輸出

**應用程式套件：**
```csv
套件名稱,引用套件名稱,套件 Repo URL,License 名稱,License URL,備註
express,[直接依賴],https://github.com/expressjs/express,MIT License,https://github.com/expressjs/express/blob/master/LICENSE,
lodash,[直接依賴],https://github.com/lodash/lodash,Other,https://github.com/lodash/lodash/blob/main/LICENSE,
```

**OS 系統套件：**
```csv
套件名稱,安裝來源,套件 URL,License 名稱,License URL,VCS URL,備註
imagemagick,[直接依賴],https://tracker.debian.org/pkg/imagemagick,"ImageMagick
GPL-2.0-or-later",https://sources.debian.org/.../copyright,https://salsa.debian.org/debian/imagemagick,
```

## 支援的 License 類型

本工具支援 [GitHub 官方定義的 License 類型](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository#searching-github-by-license-type)：

| 授權名稱 | SPDX ID |
|---------|---------|
| Academic Free License v3.0 | `AFL-3.0` |
| Apache License 2.0 | `Apache-2.0` |
| Artistic License 2.0 | `Artistic-2.0` |
| Boost Software License 1.0 | `BSL-1.0` |
| BSD 2-Clause "Simplified" License | `BSD-2-Clause` |
| BSD 3-Clause "New" or "Revised" License | `BSD-3-Clause` |
| BSD 3-Clause Clear License | `BSD-3-Clause-Clear` |
| BSD 4-Clause "Original" or "Old" License | `BSD-4-Clause` |
| BSD Zero Clause License | `0BSD` |
| Creative Commons License Family | `CC` |
| Creative Commons Zero v1.0 Universal | `CC0-1.0` |
| Creative Commons Attribution 4.0 | `CC-BY-4.0` |
| Creative Commons Attribution ShareAlike 4.0 | `CC-BY-SA-4.0` |
| Do What The F*ck You Want To Public License | `WTFPL` |
| Educational Community License v2.0 | `ECL-2.0` |
| Eclipse Public License 1.0 | `EPL-1.0` |
| Eclipse Public License 2.0 | `EPL-2.0` |
| European Union Public License 1.1 | `EUPL-1.1` |
| GNU Affero General Public License v3.0 | `AGPL-3.0` |
| GNU General Public License Family | `GPL` |
| GNU General Public License v2.0 | `GPL-2.0` |
| GNU General Public License v3.0 | `GPL-3.0` |
| GNU Lesser General Public License Family | `LGPL` |
| GNU Lesser General Public License v2.1 | `LGPL-2.1` |
| GNU Lesser General Public License v3.0 | `LGPL-3.0` |
| ISC License | `ISC` |
| LaTeX Project Public License v1.3c | `LPPL-1.3c` |
| Microsoft Public License | `MS-PL` |
| MIT License | `MIT` |
| Mozilla Public License 2.0 | `MPL-2.0` |
| Open Software License 3.0 | `OSL-3.0` |
| PostgreSQL License | `PostgreSQL` |
| SIL Open Font License 1.1 | `OFL-1.1` |
| University of Illinois/NCSA Open Source License | `NCSA` |
| The Unlicense | `Unlicense` |
| zLib License | `Zlib` |

## 備註說明

CSV 中的「備註」欄位可能包含以下資訊：

| 備註內容 | 說明 |
|---------|------|
| `非標準 (MIT)` | License 被識別為 MIT，但內容與標準模板有差異 |
| `非 GitHub 來源` | Repository 不在 GitHub 上 |
| `無法取得` | 無法從 registry 或 GitHub 取得資訊 |
| `License type could not be determined` | GitHub 無法識別 License 類型 |

## 開發

### 執行測試

```bash
# 安裝依賴
pip install -r requirements.txt

# 執行測試
pytest tests/ -v
```

### 測試檔案

測試用的 fixture 檔案位於 `tests/fixtures/` 目錄：
- `yarn.lock` - JavaScript/Node.js 測試檔案
- `package.json` - npm 直接依賴定義
- `Gemfile.lock` - Ruby 測試檔案
- `requirements.txt` - Python 測試檔案
- `Dockerfile` - Debian-based Dockerfile 測試檔案

## License

MIT License

