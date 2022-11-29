import os
import re

from rethinkdb import RethinkDB
from jose import jwt
from jose.exceptions import JWTError
from datetime import datetime
from passlib.hash import pbkdf2_sha256

from flask import g, current_app

from api.utils.errors import (
    ValidationError,
    DatabaseProcessError,
    UnavailableContentError,
)

r = RethinkDB()


class RethinkDBModel(object):
    @classmethod
    def find(cls, id):
        return r.table(cls._table).get(id).run(g.conn)

    @classmethod
    def filter(cls, predicate):
        return list(r.table(cls._table).filter(predicate).run(g.conn))

    @classmethod
    def update(cls, id, fields):
        status = r.table(cls._table).get(id).update(fields).run(g.conn)
        if status["errors"]:
            raise DatabaseProcessError("Could not complete the update action")
        return True

    @classmethod
    def delete(cls, id):
        status = r.table(cls._table).get(id).delete().run(g.conn)
        if status["errors"]:
            raise DatabaseProcessError("Could not complete the delete action")
        return True

    @classmethod
    def update_where(cls, predicate, fields):
        status = r.table(cls._table).filter(predicate).update(fields).run(g.conn)
        if status["errors"]:
            raise DatabaseProcessError("Could not complete the update action")
        return True

    @classmethod
    def delete_where(cls, predicate):
        status = r.table(cls._table).filter(predicate).delete().run(g.conn)
        if status["errors"]:
            raise DatabaseProcessError("Could not complete the delete action")
        return True


class User(RethinkDBModel):
    _table = "users"

    @classmethod
    def create(cls, **kwargs):
        fullname = kwargs.get("fullname")
        email = kwargs.get("email")
        password = kwargs.get("password")
        password_conf = kwargs.get("password_conf")
        if password != password_conf:
            raise ValidationError(
                "Password and Confirm password need to be the same value"
            )
        password = cls.hash_password(password)
        doc = {
            "fullname": fullname,
            "email": email,
            "password": password,
            "date_created": datetime.now(r.make_timezone("+01:00")),
            "date_modified": datetime.now(r.make_timezone("+01:00")),
        }
        r.table(cls._table).insert(doc).run(g.conn)

    @classmethod
    def validate(cls, email, password):
        docs = list(r.table(cls._table).filter({"email": email}).run(g.conn))

        if not len(docs):
            raise ValidationError("Could not find the e-mail address you specified")

        _hash = docs[0]["password"]

        if cls.verify_password(password, _hash):
            try:
                user_id = docs[0]["id"]
                token = jwt.encode(
                    {"id": user_id},
                    current_app.config["SECRET_KEY"],
                    algorithm="HS256",
                )
                return (user_id, token)
            except JWTError:
                raise ValidationError(
                    "There was a problem while trying to create a JWT token."
                )
        else:
            raise ValidationError("The password you inputed was incorrect.")

    @staticmethod
    def hash_password(password):
        return pbkdf2_sha256.encrypt(password, rounds=200000, salt_size=16)

    @staticmethod
    def verify_password(password, _hash):
        return pbkdf2_sha256.verify(password, _hash)


class File(RethinkDBModel):
    _table = "files"

    @classmethod
    def create(cls, **kwargs):
        name = kwargs.get("name")
        size = kwargs.get("size")
        uri = kwargs.get("uri")
        parent = kwargs.get("parent")
        creator = kwargs.get("creator")

        # Direct parent ID
        parent_id = "0" if parent is None else parent["id"]

        doc = {
            "name": name,
            "size": size,
            "uri": uri,
            "parent_id": parent_id,
            "creator": creator,
            "is_folder": False,
            "status": True,
            "date_created": datetime.now(r.make_timezone("+01:00")),
            "date_modified": datetime.now(r.make_timezone("+01:00")),
        }

        res = r.table(cls._table).insert(doc).run(g.conn)
        doc["id"] = res["generated_keys"][0]

        if parent is not None:
            Folder.add_object(parent, doc["id"])

        return doc

    @classmethod
    def find(cls, id, listing=False):
        file_ref = r.table(cls._table).get(id).run(g.conn)
        if file_ref is not None:
            if file_ref["is_folder"] and listing and file_ref["objects"] is not None:
                file_ref["objects"] = list(
                    r.table(cls._table).get_all(r.args(file_ref["objects"])).run(g.conn)
                )
        return file_ref

    @classmethod
    def move(cls, obj, to):
        previous_folder_id = obj["parent_id"]
        previous_folder = Folder.find(previous_folder_id)
        Folder.remove_object(previous_folder, obj["id"])
        Folder.add_object(to, obj["id"])


class Folder(File):
    @classmethod
    def create(cls, **kwargs):
        name = kwargs.get("name")
        parent = kwargs.get("parent")
        creator = kwargs.get("creator")

        # Direct parent ID
        parent_id = "0" if parent is None else parent["id"]

        doc = {
            "name": name,
            "parent_id": parent_id,
            "creator": creator,
            "is_folder": True,
            "last_index": 0,
            "status": True,
            "objects": None,
            "date_created": datetime.now(r.make_timezone("+01:00")),
            "date_modified": datetime.now(r.make_timezone("+01:00")),
        }

        res = r.table(cls._table).insert(doc).run(g.conn)
        doc["id"] = res["generated_keys"][0]

        if parent is not None:
            cls.add_object(parent, doc["id"], True)

        cls.tag_folder(parent, doc["id"])

        return doc

    @classmethod
    def move(cls, obj, to):
        if to is not None:
            parent_tag = to["tag"]
            child_tag = obj["tag"]

            parent_sections = parent_tag.split("#")
            child_sections = child_tag.split("#")

            if len(parent_sections) > len(child_sections):
                matches = re.match(child_tag, parent_tag)
                if matches is not None:
                    raise Exception(
                        "You can't move this object to the specified folder"
                    )

        previous_folder_id = obj["parent_id"]
        previous_folder = cls.find(previous_folder_id)
        cls.remove_object(previous_folder, obj["id"])

        if to is not None:
            cls.add_object(to, obj["id"], True)

    @classmethod
    def remove_object(cls, folder, object_id):
        update_fields = folder["objects"] or []
        while object_id in update_fields:
            update_fields.remove(object_id)
        cls.update(folder["id"], {"objects": update_fields})

    @classmethod
    def add_object(cls, folder, object_id, is_folder=False):
        p = {}
        update_fields = folder["objects"] or []
        update_fields.append(object_id)
        if is_folder:
            p["last_index"] = folder["last_index"] + 1
        p["objects"] = update_fields
        cls.update(folder["id"], p)

    @classmethod
    def tag_folder(cls, parent, id):
        tag = (
            id
            if parent is None
            else "{}#{}".format(parent["tag"], parent["last_index"])
        )
        cls.update(id, {"tag": tag})
