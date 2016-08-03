import os

from jose import jwt
from functools import wraps

from flask import request, current_app
from flask_restful import reqparse, abort, Resource
from werkzeug import secure_filename

from api.models import User, File
from api.utils.errors import ValidationError

BASE_DIR = os.path.abspath(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
)

ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

def login_required(f):
    @wraps(f)
    def func(*args, **kwargs):
        if 'authorization' in request.headers:
            try:
                token = request.headers.get('authorization')
                payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            except Exception as e:
                abort(400, message="There was a problem while trying to parse your token -> {}".format(e.message))
        token = request.headers()
    return func

def validate_user(f):
    @wraps(f)
    def func(*args, **kwargs):
        user_id = kwargs.get('user_id')
        try:
            user = User.find(user_id)
            # Store the user in a globally accepted variable
            return f(*args, **kwargs)
        except:
            abort(400, message="There was a problem while trying to get this user. The user might not exist")
    return func

def is_allowed(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


class CreateList(Resource):
    @validate_user
    def get(self, user_id):
        try:
            return File.search({'creator': user_id})
        except Exception as e:
            abort(500, message="There was an error while trying to get your files --> {}".format(e.message))

    @validate_user
    def post(self, user_id):
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('parent', type=int, help='This should be the parent folder id')
            
            args = parser.parse_args()
            
            folder = args.get('folder', 0)

            if not File.is_folder(folder):
                raise Exception("This folder does not exist")
            
            files = request.files['file']
           
            if files and is_allowed(files.filename):
                _dir = os.path.join(BASE_DIR, 'upload/{}/'.format(user_id))

                # Create this directory if it doesn't already exist
                if not os.path.isdir(_dir):
                    os.mkdir(_dir)

                filename = secure_filename(files.filename)
                to_path = os.path.join(_dir, filename)
                files.save(to_path)
                fileuri = os.path.join('upload/{}/'.format(user_id), filename)
                filesize = os.path.getsize(to_path)

                return File.create(
                    name=filename,
                    uri=fileuri,
                    size=filesize,
                    parent=folder,
                    creator=user_id
                )
        except Exception as e:
            abort(500, message="There was an while processing your request --> {}".format(e.message))
