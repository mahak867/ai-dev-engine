import os
class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-secret-change-in-prod')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
    CORS_ORIGINS = ['http://localhost:5173', 'http://localhost:3000']