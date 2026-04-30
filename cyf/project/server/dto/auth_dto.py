import re
from dataclasses import dataclass


@dataclass
class LoginRequest:
    user: str
    password: str

    @classmethod
    def from_data(cls, data):
        return cls(user=str(data.get("user", "")).strip(), password=str(data.get("password", "")).strip())


@dataclass
class RefreshTokenRequest:
    refresh_token: str

    @classmethod
    def from_data(cls, data):
        return cls(refresh_token=str(data.get("refresh_token", "")).strip())


@dataclass
class RegisterRequest:
    username: str
    password: str
    api_key: str

    @classmethod
    def from_data(cls, data):
        return cls(
            username=str(data.get("username", "")).strip(),
            password=str(data.get("password", "")).strip(),
            api_key=str(data.get("api_key", "")).strip(),
        )

    def validate(self):
        if not self.username:
            return "用户名不能为空"
        if len(self.username) < 3 or len(self.username) > 20:
            return "用户名长度必须在3-20个字符之间"
        if not re.match(r"^[a-zA-Z0-9_]+$", self.username):
            return "用户名只能包含字母、数字和下划线"
        if not self.password:
            return "密码不能为空"
        if len(self.password) < 6:
            return "密码长度至少为6位"
        return None


@dataclass
class ResetPasswordRequest:
    current_password: str
    new_password: str
    new_api_key: str

    @classmethod
    def from_data(cls, data):
        return cls(
            current_password=str(data.get("current_password", "")).strip(),
            new_password=str(data.get("new_password", "")).strip(),
            new_api_key=str(data.get("new_api_key", "")).strip(),
        )
