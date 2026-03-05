import os
import time
import asyncio

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

    host     = os.getenv("MYSQL_HOST", "db")
    port     = os.getenv("MYSQL_PORT", "3306")
    user     = os.getenv("MYSQL_USER", "refbot")
    password = os.getenv("MYSQL_PASSWORD", "")
    db       = os.getenv("MYSQL_DB", "refbot_db")

    cmd = (
        f"mysqldump -h {host} -P {port} -u {user} "
        f"-p{password} {db} > {filename}"
    )

    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
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
