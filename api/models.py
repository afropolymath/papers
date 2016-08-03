import os
import rethinkdb as r
from jose import jwt
from jose.exceptions import JWTError
from datetime import datetime
from passlib.hash import pbkdf2_sha256

from flask import current_app

from api.utils.errors import ValidationError, DatabaseProcessError, UnavailableContentError

conn = r.connect(db="papers")

class RethinkDBModel(object):
    @classmethod
    def find(cls, id):
        return r.table(cls._table).get(id).run(conn)


class User(RethinkDBModel):
    _table = 'users'

    @classmethod
    def create(cls, **kwargs):
        fullname = kwargs.get('fullname')
        email = kwargs.get('email')
        password = kwargs.get('password')
        password_conf = kwargs.get('password_conf')
        if password != password_conf:
            raise ValidationError("Password and Confirm password need to be the same value")
        password = cls.hash_password(password)
        doc = {
            'fullname': fullname,
            'email': email,
            'password': password,
            'date_created': r.now(),
            'date_modified': r.now()
        }
        r.table(cls._table).insert(doc).run(conn)

    @classmethod
    def validate(cls, email, password):
        docs = list(r.table(cls._table).filter({'email': email}).run(conn))

        if not len(docs):
            raise ValidationError("Could not find the e-mail address you specified")

        _hash = doc[0]['password']

        if cls.verify_password(password, _hash):
            try:
                token = jwt.encode({'id': doc['id']}, current_app.config['SECRET_KEY'], algorithm='HS256')
                return token
            except JWTError:
                raise ValidationError("There was a problem while trying to create a JWT token.")
        else:
            raise ValidationError("The password you inputed was incorrect.")

    @staticmethod
    def hash_password(password):
        return pbkdf2_sha256.encrypt(password, rounds=200000, salt_size=16)

    @staticmethod
    def verify_password(password, _hash):
        return pbkdf2_sha256.verify(password, _hash)


class File(RethinkDBModel):
    _table = 'files'

    @classmethod
    def create(cls, **kwargs):
        name = kwargs.get('name')
        size = kwargs.get('size', 0)
        uri = kwargs.get('uri')
        parent = kwargs.get('parent')
        is_folder = kwargs.get('is_folder', False)
        creator = kwargs.get('creator')
        doc = {
            'name': name,
            'size': size,
            'uri': uri,
            'parent': parent,
            'creator': creator,
            'date_created': r.now(),
            'date_modified': r.now()
        }
        res = r.table(cls._table).insert(doc).run(conn)
        doc['id'] = res['generated_keys'][0]
        return doc

    @classmethod
    def list_folder(cls, folder_id):
        try:
            folder_properties = cls.find(folder_id)
            if folder_properties:
                contents = list(r.table(cls._table).filter({'parent': folder_id}))
                return {
                    'props': folder_properties,
                    'contents': contents
                }
        except Exception as e:
            raise ("There was an error while trying to read the folder contents -> {}".format(e.message))

    @classmethod
    def get_folder(cls, folder_id):
        res = list(r.table(cls._table).get(folder_id).run(conn))
        if len(res):
            return res
        raise UnavailableContentError("The folder you are trying to access does not exist")

    @classmethod
    def search(cls, predicate):
        return list(r.table(cls._table).filter(predicate).run(conn))

    @classmethod
    def update(cls, id, fields):
        status = r.table(cls._table).get(id).update(fields).run(conn)
        if status.errors:
            raise DatabaseProcessError("Could not complete the update action")
        return False

    @classmethod
    def delete(cls, id):
        status = r.table(cls._table).get(id).delete().run(conn)
        if status.errors:
            raise DatabaseProcessError("Could not complete the delete action")
        return False