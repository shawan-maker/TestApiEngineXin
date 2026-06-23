class DBBase:
    """数据库操作基类"""
    conn = None
    cursor = None

    def execute_sql(self, sql, params=None):
        """执行sql语句,并返回单条数据"""
        try:
            self.cursor.execute(sql, params)
            return self.cursor.fetchone()
        except Exception as e:
            raise e

    def execute_all(self, sql, params=None):
        """执行sql语句,并返回所有数据"""
        try:
            self.cursor.execute(sql, params)
            return self.cursor.fetchall()
        except Exception as e:
            raise e

    def close_db(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = None
        self.cursor = None


class MysqlDb(DBBase):
    def __init__(self, db_config):
        """mysql数据库连接"""
        import pymysql
        self.conn = pymysql.connect(**db_config, autocommit=True)
        self.cursor = self.conn.cursor(pymysql.cursors.DictCursor)


class SqlServerDb(DBBase):
    def __init__(self, db_config):
        """sqlserver数据库连接"""
        import pymssql
        self.conn = pymssql.connect(**db_config, autocommit=True)
        self.cursor = self.conn.cursor(as_dict=True)


class OracleDb(DBBase):
    def __init__(self, db_config):
        """oracle数据库连接"""
        import oracledb
        self.conn = oracledb.connect(**db_config)
        self.cursor = self.conn.cursor()


class PostgreSqlDb(DBBase):
    def __init__(self, db_config):
        """postgresql数据库连接"""
        import psycopg2
        import psycopg2.extras
        self.conn = psycopg2.connect(**db_config)
        self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


class DBClient:
    """数据库连接工具"""

    TYPE_MAP = {
        "mysql": MysqlDb,
        "sqlserver": SqlServerDb,
        "oracle": OracleDb,
        "postgresql": PostgreSqlDb,
    }

    def init_connect(self, dbs):
        if isinstance(dbs, dict):
            self._create_db(dbs)
        elif isinstance(dbs, list):
            for db in dbs:
                self._create_db(db)
        else:
            raise Exception("数据库格式配置错误")

    def _create_db(self, dbs):
        """创建数据库连接"""
        if not (dbs.get("name") and dbs.get("type") and dbs.get("config")):
            raise Exception("数据库配置错误")
        db_cls = self.TYPE_MAP.get(dbs.get("type"))
        if not db_cls:
            raise Exception(f"不支持的数据库类型: {dbs.get('type')}")
        setattr(self, dbs.get("name"), db_cls(dbs.get("config")))

    def close_db_connect(self):
        """关闭所有数据库连接"""
        for attr in list(self.__dict__):
            obj = getattr(self, attr)
            if isinstance(obj, DBBase):
                obj.close_db()
