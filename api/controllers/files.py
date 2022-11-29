import os
import re

from flask import request, g, send_from_directory
from flask_restful import reqparse, abort, Resource, fields, marshal_with
from werkzeug.utils import secure_filename

from api.models import File, Folder
from api.utils.decorators import login_required, validate_user, belongs_to_user

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

ALLOWED_EXTENSIONS = set(["txt", "pdf", "png", "jpg", "jpeg", "gif"])

file_array_serializer = {
    "id": fields.String,
    "name": fields.String,
    "size": fields.Integer,
    "uri": fields.String,
    "is_folder": fields.Boolean,
    "parent_id": fields.String,
    "creator": fields.String,
    "date_created": fields.DateTime(dt_format="rfc822"),
    "date_modified": fields.DateTime(dt_format="rfc822"),
}

file_serializer = {
    "id": fields.String,
    "name": fields.String,
    "size": fields.Integer,
    "uri": fields.String,
    "is_folder": fields.Boolean,
    "objects": fields.Nested(file_array_serializer, default=[]),
    "parent_id": fields.String,
    "creator": fields.String,
    "date_created": fields.DateTime(dt_format="rfc822"),
    "date_modified": fields.DateTime(dt_format="rfc822"),
}


def is_allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1] in ALLOWED_EXTENSIONS


class CreateList(Resource):
    @login_required
    @validate_user
    @marshal_with(file_array_serializer)
    def get(self, user_id):
        try:
            return File.filter({"creator": user_id})
        except Exception as e:
            abort(
                500,
                message="There was an error while trying to get your files --> {}".format(
                    e.message
                ),
            )

    @login_required
    @validate_user
    @marshal_with(file_serializer)
    def post(self, user_id):
        try:
            parser = reqparse.RequestParser()
            parser.add_argument(
                "name",
                type=str,
                help="This should be the folder name if creating a folder",
            )
            parser.add_argument(
                "parent_id", type=str, help="This should be the parent folder id"
            )
            parser.add_argument(
                "is_folder",
                type=bool,
                help="This indicates whether you are trying to create a folder or not",
            )

            args = parser.parse_args()

            name = args.get("name", None)
            parent_id = args.get("parent_id", None)
            is_folder = args.get("is_folder", False)

            parent = None

            # Are we adding this to a parent folder?
            if parent_id is not None:
                parent = File.find(parent_id)
                if parent is None:
                    raise Exception("This folder does not exist")
                if not parent["is_folder"]:
                    raise Exception("Select a valid folder to upload to")
            # Are we creating a folder?
            if is_folder:
                if name is None:
                    raise Exception("You need to specify a name for this folder")

                return Folder.create(
                    name=name, parent=parent, is_folder=is_folder, creator=user_id
                )
            else:
                files = request.files["file"]

                if files and is_allowed(files.filename):
                    _dir = os.path.join(BASE_DIR, "upload/{}/".format(user_id))

                    if not os.path.isdir(_dir):
                        os.mkdir(_dir)

                    filename = secure_filename(files.filename)
                    to_path = os.path.join(_dir, filename)
                    files.save(to_path)
                    fileuri = os.path.join("upload/{}/".format(user_id), filename)
                    filesize = os.path.getsize(to_path)

                    return File.create(
                        name=filename,
                        uri=fileuri,
                        size=filesize,
                        parent=parent,
                        creator=user_id,
                    )
                raise Exception("You did not supply a valid file in your request")
        except Exception as e:
            print(e)
            abort(
                500,
                message="There was an error while processing your request --> {}".format(
                    e
                ),
            )


class ViewEditDelete(Resource):
    @login_required
    @validate_user
    @belongs_to_user
    @marshal_with(file_serializer)
    def get(self, user_id, file_id):
        try:
            should_download = request.args.get("download", False)
            if should_download == "true":
                parts = os.path.split(g.file["uri"])
                return send_from_directory(directory=parts[0], filename=parts[1])
            return g.file
        except Exception as e:
            abort(
                500,
                message="There was an while processing your request --> {}".format(
                    e.message
                ),
            )

    @login_required
    @validate_user
    @belongs_to_user
    @marshal_with(file_serializer)
    def put(self, user_id, file_id):
        try:
            update_fields = {}
            parser = reqparse.RequestParser()

            parser.add_argument("name", type=str, help="New name for the file/folder")
            parser.add_argument(
                "parent_id", type=str, help="New parent folder for the file/folder"
            )

            args = parser.parse_args()

            name = args.get("name", None)
            parent_id = args.get("parent_id", None)

            if name is not None:
                update_fields["name"] = name

            if parent_id is not None and g.file["parent_id"] != parent_id:
                if parent_id != "0":
                    folder_access = Folder.filter({"id": parent_id, "creator": user_id})
                    if not folder_access:
                        abort(
                            404,
                            message="You don't have access to the folder you're trying to move this object to",
                        )

                if g.file["is_folder"]:
                    update_fields["tag"] = (
                        g.file["id"]
                        if parent_id == "0"
                        else "{}#{}".format(folder_access["tag"], folder["last_index"])
                    )
                    Folder.move(g.file, folder_access)
                else:
                    File.move(g.file, folder_access)

                update_fields["parent_id"] = parent_id

            if g.file["is_folder"]:
                Folder.update(file_id, update_fields)
            else:
                File.update(file_id, update_fields)

            return File.find(file_id)
        except Exception as e:
            abort(
                500,
                message="There was an while processing your request --> {}".format(
                    e.message
                ),
            )

    @login_required
    @validate_user
    @belongs_to_user
    def delete(self, user_id, file_id):
        try:
            hard_delete = request.args.get("hard_delete", False)
            if not g.file["is_folder"]:
                if hard_delete == "true":
                    os.remove(g.file["uri"])
                    File.delete(file_id)
                else:
                    File.update(file_id, {"status": False})
            else:
                if hard_delete == "true":
                    folders = Folder.filter(
                        lambda folder: folder["tag"].startswith(g.file["tag"])
                    )
                    for folder in folders:
                        files = File.filter(
                            {"parent_id": folder["id"], "is_folder": False}
                        )
                        File.delete({"parent_id": folder["id"], "is_folder": False})
                        for f in files:
                            os.remove(f["uri"])
                else:
                    File.update(file_id, {"status": False})
                    File.update({"parent_id": file_id}, {"status": False})
            return "File has been deleted successfully", 204
        except:
            abort(
                500,
                message="There was an error while processing your request --> {}".format(
                    e.message
                ),
            )
