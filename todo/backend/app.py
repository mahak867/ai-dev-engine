from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from extensions import db, bcrypt, jwt
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    CORS(app, origins=app.config['CORS_ORIGINS'], supports_credentials=True)
    
    # Import ALL models before create_all
    from models import Todo, User
    
    # Register blueprints
    from routes.main import main_bp
    app.register_blueprint(main_bp, url_prefix='/api/v1')
    
    # Health check
    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'version': '1.0.0'})
    
    with app.app_context():
        db.create_all()
    
    return app

app = create_app()
if __name__ == '__main__':
    app.run(debug=True, port=5000)