"""Load an already installed spatial extension, with auto-download disabled."""
import duckdb
from .territory import ROOT


def connect(memory_limit='1GB'):
    if duckdb.__version__ != '1.5.5':
        raise RuntimeError('Pinned DuckDB 1.5.5 required')
    extension = ROOT / 'data/cache/duckdb/extensions/v1.5.5/windows_amd64/spatial.duckdb_extension'
    if not extension.is_file():
        raise FileNotFoundError('An approved local spatial extension is required')
    temporary = ROOT / 'data/cache/duckdb/tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(config={'autoinstall_known_extensions': 'false', 'autoload_known_extensions': 'false', 'memory_limit': memory_limit, 'threads': '2', 'temp_directory': str(temporary)})
    connection.execute('SET enable_progress_bar=false')
    connection.execute("LOAD '" + extension.as_posix().replace("'", "''") + "'")
    return connection
