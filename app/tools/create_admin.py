import os

from dotenv import load_dotenv

from app.api.auth import get_password_hash
from app.db import engine, SessionLocal
from app.models import Base, User

load_dotenv()


def create_admin():
    # Гарантовано створюємо таблиці (якщо вони ще не створені)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    password = os.getenv("ADMIN_PIN", "")
    print(password)
    try:
        if existing := db.query(User).filter(User.username == "admin").first():
            print("Користувач 'admin' вже існує. Оновлюємо пароль та роль...")
            existing.password_hash = get_password_hash(password)
            existing.role = "admin"
            db.commit()
            print("Дані адміністратора успішно оновлено.")
            return

        # Створюємо нового адміна
        hashed_password = get_password_hash(password)
        admin_user = User(username="admin", password_hash=hashed_password, role="admin")

        db.add(admin_user)
        db.commit()
        print("Адміністратора успішно створено!")
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
