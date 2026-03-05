import os
import time
import asyncio
from db_config import get_db_settings

BACKUP_DIR = "backups"


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


async def make_mysql_backup() -> str:
    """
    MySQL dump oladi va backups/ papkasiga saqlaydi.
    mysqldump kerak (Docker da mysql-client o'rnatilgan bo'ladi).
    """
    _ensure_backup_dir()
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(BACKUP_DIR, f"backup_{ts}.sql")

    host, port, user, password, db = get_db_settings()

    env = os.environ.copy()
    env["MYSQL_PWD"] = password

    with open(filename, "wb") as dump_out:
        proc = await asyncio.create_subprocess_exec(
            "mysqldump",
            "-h", host,
            "-P", str(port),
            "-u", user,
            db,
            stdout=dump_out,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        _, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = (stderr or b"").decode("utf-8", errors="ignore").strip()
        raise RuntimeError("mysqldump failed: " + err)

    return filename


def cleanup_old_backups(keep: int = 30):
    import glob
    _ensure_backup_dir()
    files = sorted(glob.glob(os.path.join(BACKUP_DIR, "backup_*.sql")))
    for old in files[:-keep]:
        try:
            os.remove(old)
        except Exception:
            pass
