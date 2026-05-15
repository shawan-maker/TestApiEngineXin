import pymysql,pymssql

class DBBase:
    """数据库操作类"""
    conn = None
    cursor = None

    def execute_sql(self, sql, params=None):
        """执行sql语句,并返回单条数据"""
        try:
            self.cursor.execute(sql, params)
            return self.cursor.fetchone()
        except Exception as e:
            raise e

    def execute_all(self,sql, params=None):
        """执行sql语句,并返回所有数据"""
        try:
            self.cursor.execute(sql, params)
            return self.cursor.fetchall()
        except Exception as e:
            raise e

    def close_db(self):
        """关闭数据库连接"""
        try:
            if self.cursor:
                self.cursor.close()
        except Exception:
            pass
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        self.cursor = None
        self.conn = None


class MysqlDb(DBBase):
    def __init__(self,db_config):
        """mysql数据库连接"""
        self.conn = pymysql.connect(**db_config,autocommit=True)
        self.cursor = self.conn.cursor(pymysql.cursors.DictCursor)

class SqlServerDb(DBBase):
    def __init__(self,db_config):
        """sqlserver数据库连接"""
        self.conn = pymssql.connect(**db_config,autocommit=True)
        self.cursor = self.conn.cursor(as_dict=True)

# class OracleDb(DBBase):
#     """mysql数据库操作类"""
#     def __init__(self,db_config):
#         # 连接数据库
#         self.conn = cx_Oracle.connect(**db_config)
#         self.cursor = self.conn.cursor()

class DBClient:
    """数据库连接工具"""
    def init_connent(self,dbs):
        if isinstance(dbs,dict):
            self.create_db_connect(dbs)
        elif isinstance(dbs,list):
            for db in dbs:
                self.create_db_connect(db)
        else:
            raise Exception("数据库格式配置错误")

    def create_db_connect(self,dbs):
        """创建数据库连接"""
        # 1、如果配置不正确，则抛出异常
        if not (dbs.get("name") and dbs.get("type") and dbs.get("config")):
            raise Exception("数据库配置错误")
        if dbs.get("type") == "mysql":
            setattr(self,dbs.get("name"),MysqlDb(dbs.get("config")))
        elif dbs.get("type") == "sqlserver":
            setattr(self, dbs.get("name"), SqlServerDb(dbs.get("config")))
        else:
            raise Exception("不支持的数据库类型")

    def close_db_connent(self):
        """关闭数据库连接"""
        for db in self.__dict__:
            if isinstance(getattr(self,db),DBBase):
                getattr(self,db).close_db()

if __name__ == '__main__':
    items = [
        {
            "name": "P2P",
            "type": "mysql",
            "config": {
                "host": "121.43.169.97",
                "port": 3306,
                "user": "student",
                "password": "P2P_student_2023"
            }
        }
    ]
    db = DBClient()
    db.init_connent(items)
    print(db.P2P.execute_sql("SELECT * FROM czbk_member.mb_member;"))