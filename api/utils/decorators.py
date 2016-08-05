from jose import jwt
from jose.exceptions import JWTError
from functools import wraps

from flask import current_app, request, g
from flask_restful import abort

from api.models import User, File

def login_required(f):
    '''
    This decorator checks the header to ensure a valid token is set
    '''
    @wraps(f)
    def func(*args, **kwargs):
        try:
            if 'authorization' not in request.headers:
                abort(404, message="You need to be logged in to access this resource")
            token = request.headers.get('authorization')
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['id']
            g.user = User.find(user_id)
            if g.user is None:
               abort(404, message="The user id is invalid")
            return f(*args, **kwargs)
        except JWTError as e:
            abort(400, message="There was a problem while trying to parse your token -> {}".format(e.message))
    return func

def validate_user(f):
    '''
    This decorate ensures that the user logged in is the actually the same user we're operating on
    '''
    @wraps(f)
    def func(*args, **kwargs):
        user_id = kwargs.get('user_id')
        if user_id != g.user['id']:
            abort(404, message="You do not have permission to the resource you are trying to access")
        return f(*args, **kwargs)
    return func

def belongs_to_user(f):
    '''
    This decorator ensures that the file we're trying to access actually belongs to us
    '''
    @wraps(f)
    def func(*args, **kwargs):
        file_id = kwargs.get('file_id')
        user_id = kwargs.get('user_id')
        file = File.find(file_id, True)
        if not file or file['creator'] != user_id:
            abort(404, message="The file you are trying to access was not found")
        g.file = file
        return f(*args, **kwargs)
    return func