# update_password.py
import sqlite3
import getpass
from passlib.context import CryptContext

# Configuração do Passlib (igual à sua API)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB_NAME = "diagprooff.db"

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_NAME)
        return conn
    except sqlite3.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

def update_admin_password():
    username = input("Digite o nome de usuário para atualizar (ex: admin): ")
    password = getpass.getpass(f"Digite a nova senha para '{username}': ")
    
    conn = get_db_connection()
    if conn is None:
        return
        
    try:
        cursor = conn.cursor()
        
        # Criptografa a nova senha com o método da API
        hashed_password = pwd_context.hash(password)
        
        # Atualiza a senha no banco de dados
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hashed_password, username)
        )
        
        if cursor.rowcount == 0:
            print(f"\nERRO: Usuário '{username}' não encontrado no banco de dados.")
        else:
            conn.commit()
            print(f"\nSUCESSO! A senha para o usuário '{username}' foi atualizada para o novo formato.")
            
    except sqlite3.Error as e:
        print(f"Ocorreu um erro no banco de dados: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    update_admin_password()