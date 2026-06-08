# FigureChain

## figure-data

`figure-data` 是本仓库当前的数据导入与验证工具。第一阶段只导入本地 CBDB
SQLite 快照到 PostgreSQL `figure_data` schema，并提供基础人物搜索与导入验收命令。

## 本地配置

创建 `.env`：

```text
DATABASE_URL=<local PostgreSQL connection string>
```

不要提交 `.env`、完整数据库连接串、密码或本机固定路径。

## 常用命令

```bash
uv sync
uv run alembic upgrade head
uv run figure-data import-cbdb --sqlite figure-data/cbdb_20260530.sqlite3
uv run figure-data search-person "诸葛亮"
uv run figure-data validate-cbdb
uv run figure-data validate-encounters
```

如果本机没有把 `uv` 放进 PATH，也可以使用项目虚拟环境中的命令：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\figure-data.exe import-cbdb --sqlite figure-data\cbdb_20260530.sqlite3
.\.venv\Scripts\figure-data.exe search-person "诸葛亮"
.\.venv\Scripts\figure-data.exe validate-cbdb
.\.venv\Scripts\figure-data.exe validate-encounters
```

## 验证

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run figure-data validate-cbdb
uv run figure-data validate-encounters
```

`validate-cbdb` 会检查本地 SQLite 快照核心表行数，并对一组样例人物执行搜索命中验证。
`validate-encounters` 会检查已提升 encounter 的一致性；在尚未提升任何 encounter
时，所有基础一致性检查应通过。
