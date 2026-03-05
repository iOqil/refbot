import os
import aiomysql

# MySQL sozlamalari .env dan
DB_HOST     = os.getenv("MYSQL_HOST", "localhost")
DB_PORT     = int(os.getenv("MYSQL_PORT", "3306"))
DB_USER     = os.getenv("MYSQL_USER", "refbot")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DB_NAME     = os.getenv("MYSQL_DB", "refbot_db")

# Global connection pool
_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
            autocommit=True,
            charset="utf8mb4",
            minsize=1,
            maxsize=10
        )
    return _pool


async def execute(query: str, args=None, fetch=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, args or ())
            if fetch == "one":
                return await cur.fetchone()
            if fetch == "all":
                return await cur.fetchall()
            return None


# ---------- DB INIT ----------

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:

            await cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                full_name VARCHAR(255),
                pending_referrer_id BIGINT DEFAULT NULL,
                referrer_id BIGINT DEFAULT NULL,
                joined_at BIGINT
            ) CHARACTER SET utf8mb4
            """)

            await cur.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                invited_id BIGINT PRIMARY KEY,
                referrer_id BIGINT NOT NULL,
                created_at BIGINT,
                active TINYINT(1) NOT NULL DEFAULT 1
            ) CHARACTER SET utf8mb4
            """)

            await cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                `key` VARCHAR(100) PRIMARY KEY,
                value TEXT NOT NULL
            ) CHARACTER SET utf8mb4
            """)

            await cur.execute("""
            INSERT IGNORE INTO settings(`key`, value)
            VALUES ('contest_status', 'running')
            """)

        await conn.commit()


# ---------- SETTINGS ----------

async def get_setting(key: str):
    row = await execute(
        "SELECT value FROM settings WHERE `key`=%s", (key,), fetch="one"
    )
    return row[0] if row else None


async def set_setting(key: str, value: str):
    await execute("""
    INSERT INTO settings(`key`, value) VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE value=VALUES(value)
    """, (key, value))


# ---------- USERS ----------

async def upsert_user(user_id: int, username: str, full_name: str, ts: int):
    await execute("""
    INSERT INTO users (user_id, username, full_name, joined_at)
    VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        username=VALUES(username),
        full_name=VALUES(full_name)
    """, (user_id, username, full_name, ts))


async def get_user(user_id: int):
    return await execute("""
    SELECT user_id, username, full_name,
           pending_referrer_id, referrer_id
    FROM users WHERE user_id=%s
    """, (user_id,), fetch="one")


async def referrer_exists(user_id: int) -> bool:
    row = await execute(
        "SELECT 1 FROM users WHERE user_id=%s", (user_id,), fetch="one"
    )
    return row is not None


async def set_pending_referrer(invited_id: int, pending_referrer_id: int):
    await execute("""
    UPDATE users SET pending_referrer_id=%s WHERE user_id=%s
    """, (pending_referrer_id, invited_id))


async def get_all_user_ids() -> list:
    rows = await execute("SELECT user_id FROM users", fetch="all")
    return [r[0] for r in rows] if rows else []


# ---------- REFERRALS ----------

async def confirm_referral(invited_id: int, referrer_id: int, ts: int) -> bool:
    if invited_id == referrer_id:
        return False

    existing = await execute(
        "SELECT referrer_id, active FROM referrals WHERE invited_id=%s",
        (invited_id,), fetch="one"
    )

    if existing:
        existing_referrer, is_active = existing
        if is_active == 1:
            return False
        # Qayta faollashtirish
        await execute("""
        UPDATE referrals SET active=1, created_at=%s WHERE invited_id=%s
        """, (ts, invited_id))
        await execute("""
        UPDATE users SET referrer_id=%s, pending_referrer_id=NULL WHERE user_id=%s
        """, (existing_referrer, invited_id))
    else:
        # Yangi referral
        await execute("""
        INSERT INTO referrals (invited_id, referrer_id, created_at, active)
        VALUES (%s, %s, %s, 1)
        """, (invited_id, referrer_id, ts))
        await execute("""
        UPDATE users SET referrer_id=%s, pending_referrer_id=NULL WHERE user_id=%s
        """, (referrer_id, invited_id))

    return True


async def deactivate_referral(invited_id: int):
    await execute(
        "UPDATE referrals SET active=0 WHERE invited_id=%s", (invited_id,)
    )
    await execute(
        "UPDATE users SET referrer_id=NULL WHERE user_id=%s", (invited_id,)
    )


async def get_all_confirmed_referrals() -> list:
    rows = await execute(
        "SELECT invited_id, referrer_id FROM referrals WHERE active=1",
        fetch="all"
    )
    return rows if rows else []


async def referral_count(user_id: int) -> int:
    row = await execute("""
    SELECT COUNT(*) FROM referrals WHERE referrer_id=%s AND active=1
    """, (user_id,), fetch="one")
    return row[0] if row else 0


async def top_referrers(limit: int = 10):
    rows = await execute("""
    SELECT r.referrer_id, COUNT(*) as cnt
    FROM referrals r
    WHERE r.active=1
    GROUP BY r.referrer_id
    ORDER BY cnt DESC
    LIMIT %s
    """, (limit,), fetch="all")

    result = []
    for uid, cnt in (rows or []):
        u = await execute(
            "SELECT username, full_name FROM users WHERE user_id=%s",
            (uid,), fetch="one"
        )
        username = u[0] or "" if u else ""
        full_name = u[1] or "" if u else ""
        result.append((uid, username, full_name, cnt))
    return result


async def export_all_ranked():
    rows = await execute("""
    SELECT u.full_name, u.username,
           COALESCE(t.cnt, 0) as cnt
    FROM users u
    LEFT JOIN (
        SELECT referrer_id, COUNT(*) as cnt
        FROM referrals
        WHERE active=1
        GROUP BY referrer_id
    ) t ON t.referrer_id = u.user_id
    ORDER BY cnt DESC
    """, fetch="all")
    return rows if rows else []


async def reset_all_referrals():
    rows = await execute("SELECT invited_id FROM referrals", fetch="all")
    blacklist = ",".join(str(r[0]) for r in rows) if rows else ""

    await execute("DELETE FROM referrals")
    await execute("UPDATE users SET referrer_id=NULL, pending_referrer_id=NULL")
    await set_setting("referral_blacklist", blacklist)


async def is_in_blacklist(user_id: int) -> bool:
    val = await get_setting("referral_blacklist")
    if not val:
        return False
    return str(user_id) in val.split(",")


async def clear_blacklist():
    await set_setting("referral_blacklist", "")
