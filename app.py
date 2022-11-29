import inspect
import importlib
from rethinkdb import RethinkDB
from rethinkdb.errors import RqlRuntimeError, RqlDriverError
from termcolor import cprint

from flask import g, abort
from flask_cors import CORS

from api import create_app

app = create_app("development")
CORS(app)

rdb = RethinkDB()


@app.before_request
def before_request():
    try:
        g.conn = rdb.connect(
            app.config["DATABASE_HOST"],
            app.config["DATABASE_PORT"],
            db=app.config["DATABASE_NAME"],
        )
    except RqlDriverError:
        abort(503, "Database connection could be established.")


@app.teardown_request
def teardown_request(exception):
    try:
        g.rdb_conn.close()
    except AttributeError:
        pass


@app.cli.command("migrate")
def migrate():
    try:
        conn = rdb.connect(
            app.config["DATABASE_HOST"],
            app.config["DATABASE_PORT"],
            db=app.config["DATABASE_NAME"],
        )
        # Create the application tables if they do not exist
        lib = importlib.import_module("api.models")
        for cls in inspect.getmembers(lib, inspect.isclass):
            for base in cls[1].__bases__:
                if base.__name__ == "RethinkDBModel":
                    table_name = getattr(cls[1], "_table")
                    rdb.db(app.config["DATABASE_NAME"]).table_create(table_name).run(
                        conn
                    )
                    print("Created table '{}'...".format(table_name))
        print("Running RethinkDB migration command")
    except Exception as e:
        print(e)
        # cprint("An error occured --> {}".format(e.message), "red", attrs=["bold"])


if __name__ == "__main__":
    app.run(host="0.0.0.0")
