import pymysql

try:
    pymysql.install_as_MySQLdb()
    pymysql.version_info = (2, 2, 1, "final", 0)
except Exception:
    pass