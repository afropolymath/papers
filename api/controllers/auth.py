from flask_restful import reqparse, abort, Resource

from api.models import User
from api.utils.errors import ValidationError


class AuthLogin(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "email",
            type=str,
            help="You need to enter your e-mail address",
            required=True,
        )
        parser.add_argument(
            "password", type=str, help="You need to enter your password", required=True
        )

        args = parser.parse_args()

        email = args.get("email")
        password = args.get("password")

        try:
            (user_id, token) = User.validate(email, password)
            return {"id": user_id, "token": token}
        except ValidationError as e:
            abort(
                400,
                message="There was an error while trying to log you in -> {}".format(
                    e.message
                ),
            )


class AuthRegister(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "fullname", type=str, help="You need to enter your full name", required=True
        )
        parser.add_argument(
            "email",
            type=str,
            help="You need to enter your e-mail address",
            required=True,
        )
        parser.add_argument(
            "password",
            type=str,
            help="You need to enter your chosen password",
            required=True,
        )
        parser.add_argument(
            "password_conf",
            type=str,
            help="You need to enter the confirm password field",
            required=True,
        )

        args = parser.parse_args()

        email = args.get("email")
        password = args.get("password")
        password_conf = args.get("password_conf")
        fullname = args.get("fullname")

        try:
            User.create(
                email=email,
                password=password,
                password_conf=password_conf,
                fullname=fullname,
            )
            return {"message": "Successfully created your account."}
        except ValidationError as e:
            abort(
                400,
                message="There was an error while trying to create your account -> {}".format(
                    e.message
                ),
            )
