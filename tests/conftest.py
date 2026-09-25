import os

os.environ["LBOE_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["LBOE_REDIS_URL"] = "redis://localhost:63999/0"
os.environ["LBOE_AUTO_CREATE_SCHEMA"] = "true"
