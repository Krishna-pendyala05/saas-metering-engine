$env:POSTGRES_SERVER = "localhost"
$env:POSTGRES_PORT = "5435"
$env:PYTHONPATH = "backend"
alembic upgrade head
python -m app.db.init_db
