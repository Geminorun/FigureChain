import sqlite3
from pathlib import Path


def create_minimal_cbdb_sqlite(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table BIOG_MAIN (
            c_personid integer primary key,
            c_name_chn text,
            c_name text,
            c_birthyear integer,
            c_deathyear integer,
            c_index_year integer,
            c_female integer,
            c_dy integer,
            c_notes text
        );
        create table ALTNAME_DATA (
            c_personid integer,
            c_alt_name_chn text,
            c_alt_name text,
            c_alt_name_type_code integer
        );
        create table ASSOC_DATA (
            c_assoc_id integer primary key,
            c_personid integer,
            c_assoc_code integer,
            c_assoc_id2 integer,
            c_assoc_year integer,
            c_source integer,
            c_pages text,
            c_notes text
        );
        """
    )
    conn.execute(
        "insert into BIOG_MAIN values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (25403, "諸葛亮", "Zhuge Liang", 181, 234, 220, 0, 30, "sample"),
    )
    conn.execute(
        "insert into BIOG_MAIN values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (21204, "司馬懿", "Sima Yi", 178, 251, 230, 0, 30, "sample"),
    )
    conn.execute("insert into ALTNAME_DATA values (?, ?, ?, ?)", (25403, "孔明", "Kongming", 4))
    conn.execute(
        "insert into ASSOC_DATA values (?, ?, ?, ?, ?, ?, ?, ?)",
        (1, 25403, 95, 21204, 231, 1, "1a", "sample"),
    )
    conn.commit()
    conn.close()
    return path
