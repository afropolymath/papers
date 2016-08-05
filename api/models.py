import os
import re

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

    @classmethod
    def filter(cls, predicate):
        return list(r.table(cls._table).filter(predicate).run(conn))

    @classmethod
    def update(cls, id, fields):
        status = r.table(cls._table).get(id).update(fields).run(conn)
        if status['errors']:
            raise DatabaseProcessError("Could not complete the update action")
        return True

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

        _hash = docs[0]['password']

        if cls.verify_password(password, _hash):
            try:
                token = jwt.encode({'id': docs[0]['id']}, current_app.config['SECRET_KEY'], algorithm='HS256')
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
        size = kwargs.get('size')
        uri = kwargs.get('uri')
        parent = kwargs.get('parent')
        creator = kwargs.get('creator')

        # Direct parent ID
        parent_id = '0' if parent is None else parent['id']

        doc = {
            'name': name,
            'size': size,
            'uri': uri,
            'parent_id': parent_id,
            'creator': creator,
            'is_folder': False,
            'status': True,
            'date_created': r.now(),
            'date_modified': r.now()
        }

        res = r.table(cls._table).insert(doc).run(conn)
        doc['id'] = res['generated_keys'][0]

        if parent is not None:
            Folder.add_object(parent, doc['id'])

        return doc

    @classmethod
    def find(cls, id):
        file_ref = r.table(cls._table).get(id).run(conn)
        return file_ref

    @classmethod
    def move(cls, obj, to):
        parent_tag = to['tag']
        child_tag = obj['tag']
        previous_folder_id = obj['parent_id']
        previous_folder = Folder.find(previous_folder_id)
        cls.remove_object(previous_folder, obj['id'])
        cls.add_object(to, obj['id'])


    @classmethod
    def delete(cls, id):
        status = r.table(cls._table).get(id).delete().run(conn)
        if status['errors']:
            raise DatabaseProcessError("Could not complete the delete action")
        return True

class Folder(RethinkDBModel):
    @classmethod
    def create(cls, **kwargs):
        name = kwargs.get('name')
        parent = kwargs.get('parent')
        creator = kwargs.get('creator')

        # Determine folder tag
        parent_tag = '0' if parent is None else parent['tag']
        tag = '{}-{}'.format(parent_tag, parent['last_index'])

        # Direct parent ID
        parent_id = '0' if parent is None else parent['id']

        doc = {
            'name': name,
            'parent_id': parent_id,
            'tag': tag,
            'creator': creator,
            'is_folder': True,
            'last_index': 0,
            'status': True,
            'objects': None,
            'date_created': r.now(),
            'date_modified': r.now()
        }

        res = r.table(cls._table).insert(doc).run(conn)
        doc['id'] = res['generated_keys'][0]

        if parent is not None:
            cls.add_object(parent, doc['id'])

        return doc

    @classmethod
    def find(cls, id, listing=False):
        file_ref = r.table(cls._table).get(id).run(conn)
        if file_ref is not None:
            if listing and file_ref['objects'] is not None:
                file_ref['objects'] = list(r.table(cls._table).get_all(r.args(file_ref['objects'])).run(conn))
        return file_ref

    @classmethod
    def move(cls, obj, to):
        parent_tag = to['tag']
        child_tag = obj['tag']
        if len(parent_tag) > len(child_tag):
            matches = re.match(child_tag, parent_tag)
            if matches is not None:
                raise Exception("You can't move this object to the specified folder")
            previous_folder_id = obj['parent_id']
            previous_folder = cls.find(previous_folder_id)
            cls.remove_object(previous_folder, obj['id'])
            cls.add_object(to, obj['id'], True)

    @classmethod
    def remove_object(cls, folder, object_id):
        update_fields = folder['objects'] or []
        while object_id in update_fields:
            update_fields.remove(object_id)
        cls.update(folder['id'], {'objects': update_fields})

    @classmethod
    def add_object(cls, folder, object_id, is_folder=False):
        update_fields = folder['objects'] or []
        update_fields.append(object_id)
        if is_folder:
            last_index = folder['last_index'] + 1
        cls.update(folder['id'], {'objects': update_fields, 'last_index': last_index})

    @classmethod
    def delete(cls, id):
        status = r.table(cls._table).get(id).delete().run(conn)
        if status['errors']:
            raise DatabaseProcessError("Could not complete the delete action")
        return True
