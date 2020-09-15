import inspect
import importlib
from rethinkdb import r
from termcolor import cprint

from flask_script import Manager

from api import create_app

app = create_app('development')

manager = Manager(app)

@manager.command
def migrate():
    try:
        db_name = app.config['DATABASE_NAME']
        conn = r.connect(db=db_name)
        # Create the application tables if they do not exist
        lib = importlib.import_module('api.models')
        for cls in inspect.getmembers(lib, inspect.isclass):
            for base in cls[1].__bases__:
                if base.__name__ == "RethinkDBModel":
                    table_name = getattr(cls[1], '_table')
                    r.db('papers').table_create(table_name).run(conn)
                    print ("Created table '{}'...").format(table_name)
        print ("Running RethinkDB migration command")
    except Exception as e:
        cprint("An error occured --> {}".format(e.message), 'red', attrs=['bold'])

if __name__ == '__main__':
    manager.run()