import aiosqlite
from datetime import datetime, timezone

class DB:
    def __init__(self, path, cipher):
        self.path, self.cipher = path, cipher

    async def init(self, admin_id):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, added_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS cabinets(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, token BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS chat_history(chat_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS alert_dedup(chat_id INTEGER NOT NULL, cabinet_id INTEGER NOT NULL, date TEXT NOT NULL, PRIMARY KEY(chat_id,cabinet_id,date));
            ''')
            await db.execute('INSERT OR IGNORE INTO users(id,added_at) VALUES(?,?)', (admin_id, datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def allowed_user(self, uid):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute('SELECT 1 FROM users WHERE id=?', (uid,)) as cur:
                return await cur.fetchone() is not None

    async def allowed_group(self, gid):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute('SELECT 1 FROM groups WHERE id=?', (gid,)) as cur:
                return await cur.fetchone() is not None

    async def list_users(self):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute('SELECT id FROM users ORDER BY id') as cur:
                return [r[0] for r in await cur.fetchall()]

    async def add_user(self, uid):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT OR IGNORE INTO users VALUES(?,?)', (uid, datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def remove_user(self, uid):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('DELETE FROM users WHERE id=?', (uid,))
            await db.commit()

    async def add_group(self, gid, title):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT OR REPLACE INTO groups VALUES(?,?)', (gid, title))
            await db.commit()

    async def remove_group(self, gid):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('DELETE FROM groups WHERE id=?', (gid,))
            await db.commit()

    async def list_groups(self):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute('SELECT id,title FROM groups ORDER BY id') as cur:
                return await cur.fetchall()

    async def add_cabinet(self, name, token):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT INTO cabinets(name,token) VALUES(?,?)', (name, self.cipher.encrypt(token.encode())))
            await db.commit()

    async def remove_cabinet(self, name):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute('DELETE FROM cabinets WHERE name=?', (name,))
            await db.commit()
            return cur.rowcount

    async def cabinets(self):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute('SELECT id,name,token FROM cabinets ORDER BY name') as cur:
                rows = await cur.fetchall()
        return [(cid, name, self.cipher.decrypt(token).decode()) for cid,name,token in rows]

    async def history(self, chat_id):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute('SELECT role,content FROM chat_history WHERE chat_id=? ORDER BY created_at DESC, rowid DESC LIMIT 8', (chat_id,)) as cur:
                rows = await cur.fetchall()
        return [{'role': r, 'content': c} for r,c in reversed(rows)]

    async def append_history(self, chat_id, role, content):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT INTO chat_history VALUES(?,?,?,?)', (chat_id,role,content[:6000],datetime.now(timezone.utc).isoformat()))
            await db.execute('DELETE FROM chat_history WHERE chat_id=? AND rowid NOT IN (SELECT rowid FROM chat_history WHERE chat_id=? ORDER BY rowid DESC LIMIT 16)',(chat_id,chat_id))
            await db.commit()

    async def alert_seen(self, chat_id, cab_id, date):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute('SELECT 1 FROM alert_dedup WHERE chat_id=? AND cabinet_id=? AND date=?', (chat_id,cab_id,date)) as cur:
                return await cur.fetchone() is not None

    async def mark_alert(self, chat_id, cab_id, date):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT OR IGNORE INTO alert_dedup VALUES(?,?,?)',(chat_id,cab_id,date))
            await db.commit()
