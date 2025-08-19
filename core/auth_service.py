import sqlite3
import logging
from typing import Callable, Optional, Dict, Any

from .models import User
from werkzeug.security import generate_password_hash, check_password_hash

class AuthService:
    def __init__(self, db_connection_provider: Callable[[], sqlite3.Connection]):
        self.db_connection_provider = db_connection_provider
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_error: Optional[str] = None
        self.current_user: Optional[User] = None  # Sessão do usuário autenticado

    def _execute_commit(self, sql: str, params: tuple) -> bool:
        conn = self.db_connection_provider()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Erro ao executar comando no BD: {e}", exc_info=True)
            if conn: conn.rollback()
            self.last_error = str(e)
            return False
        finally:
            if conn: conn.close()

    def _fetch_all(self, sql: str, params: tuple = ()) -> list:
        conn = self.db_connection_provider()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            if conn: conn.close()

    def _fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        conn = self.db_connection_provider()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            if conn: conn.close()

    @staticmethod
    def hash_password(password: str) -> str:
        return generate_password_hash(password)

    def login(self, username, password) -> Optional[User]:
        """
        Tenta autenticar um usuário. Se bem-sucedido, armazena o usuário como `current_user` e retorna o objeto User.
        """
        user_data = self._fetch_one("SELECT * FROM users WHERE username = ?", (username,))
        if user_data and check_password_hash(user_data.get('password_hash', ''), password):
            self.logger.info(f"Usuário '{username}' validado com sucesso.")
            self.current_user = User(**user_data)
            return self.current_user
        self.current_user = None
        self.last_error = "Usuário ou senha inválidos."
        return None

    def logout(self):
        """Finaliza a sessão do usuário atual."""
        self.logger.info("Usuário fez logout.")
        self.current_user = None

    def get_current_user(self) -> Optional[User]:
        """Retorna o usuário autenticado atualmente (ou None)."""
        return self.current_user

    def get_last_error(self) -> Optional[str]:
        return self.last_error

    def find_user_by_username(self, username: str) -> Optional[dict]:
        return self._fetch_one("SELECT * FROM users WHERE username = ?", (username,))

    def find_user_by_id(self, user_id: int) -> Optional[dict]:
        return self._fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))

    def get_all_users(self) -> list:
        return self._fetch_all("SELECT id, username, full_name, role FROM users ORDER BY full_name")

    def create_user(self, **kwargs) -> bool:
        username = kwargs.get('username')
        password = kwargs.get('password')
        if self.find_user_by_username(username):
            self.last_error = "Nome de usuário já existe."
            return False
        hashed_password = self.hash_password(password)
        sql = """
            INSERT INTO users (username, password_hash, role, full_name, email, celular, endereco, cpf, cargo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            username, hashed_password,
            kwargs.get('role', 'user'),
            kwargs.get('full_name'),
            kwargs.get('email'),
            kwargs.get('celular'),
            kwargs.get('endereco'),
            kwargs.get('cpf'),
            kwargs.get('cargo')
        )
        return self._execute_commit(sql, params)

    def update_user(self, user_id: int, data: Dict[str, Any]) -> bool:
        fields_to_update = []
        params = []
        allowed_fields = ["full_name", "username", "email", "role", "celular", "endereco", "cpf", "cargo"]
        for field in allowed_fields:
            if field in data:
                fields_to_update.append(f"{field} = ?")
                params.append(data[field])
        if 'password' in data and data['password']:
            fields_to_update.append("password_hash = ?")
            params.append(self.hash_password(data['password']))
        if not fields_to_update:
            self.last_error = "Nenhum dado válido para atualizar."
            return False
        sql = f"UPDATE users SET {', '.join(fields_to_update)} WHERE id = ?"
        params.append(user_id)
        return self._execute_commit(sql, tuple(params))