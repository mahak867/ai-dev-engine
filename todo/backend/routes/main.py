from flask import Blueprint, request, jsonify
from models import Todo, User
def get_user_id():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return None, {'success': False, 'error': 'Missing user ID header', 'code': 'MISSING_USER_ID'}
    return int(user_id), None

main_bp = Blueprint('main', __name__)

@main_bp.route('/todos', methods=['GET'])
def get_todos():
    try:
        user_id, error = get_user_id()
        if error:
            return jsonify(error), 400
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '')
        completed = request.args.get('completed')
        
        query = Todo.query.filter_by(user_id=user_id)
        
        if search:
            query = query.filter(
                db.or_(
                    Todo.title.ilike(f'%{search}%'),
                    Todo.description.ilike(f'%{search}%')
                )
            )
        
        if completed is not None:
            query = query.filter_by(completed=completed.lower() == 'true')
        
        todos = query.paginate(page=page, per_page=per_page)
        
        data = [
            {
                'id': todo.id,
                'title': todo.title,
                'description': todo.description,
                'completed': todo.completed,
                'created_at': todo.created_at.isoformat(),
                'updated_at': todo.updated_at.isoformat(),
                'user': {
                    'id': todo.user.id,
                    'username': todo.user.username
                }
            } for todo in todos.items
        ]
        
        return jsonify({
            'success': True,
            'data': data,
            'total': todos.total,
            'page': page
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_SERVER_ERROR'
        }), 500

@main_bp.route('/todos', methods=['POST'])
def create_todo():
    try:
        user_id, error = get_user_id()
        if error:
            return jsonify(error), 400
        
        data = request.get_json()
        if not data or 'title' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required title field',
                'code': 'MISSING_TITLE'
            }), 400
        
        todo = Todo(
            title=data['title'],
            description=data.get('description'),
            completed=data.get('completed', False),
            user_id=user_id
        )
        db.session.add(todo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': {
                'id': todo.id,
                'title': todo.title,
                'description': todo.description,
                'completed': todo.completed,
                'created_at': todo.created_at.isoformat(),
                'updated_at': todo.updated_at.isoformat(),
                'user': {
                    'id': todo.user.id,
                    'username': todo.user.username
                }
            },
            'message': 'Todo created successfully'
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_SERVER_ERROR'
        }), 500

@main_bp.route('/todos/<int:id>', methods=['GET'])
def get_todo(id):
    try:
        user_id, error = get_user_id()
        if error:
            return jsonify(error), 400
        
        todo = Todo.query.filter_by(id=id, user_id=user_id).first()
        if not todo:
            return jsonify({
                'success': False,
                'error': 'Todo not found',
                'code': 'TODO_NOT_FOUND'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'id': todo.id,
                'title': todo.title,
                'description': todo.description,
                'completed': todo.completed,
                'created_at': todo.created_at.isoformat(),
                'updated_at': todo.updated_at.isoformat(),
                'user': {
                    'id': todo.user.id,
                    'username': todo.user.username
                }
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_SERVER_ERROR'
        }), 500

@main_bp.route('/todos/<int:id>', methods=['PUT'])
def update_todo(id):
    try:
        user_id, error = get_user_id()
        if error:
            return jsonify(error), 400
        
        todo = Todo.query.filter_by(id=id, user_id=user_id).first()
        if not todo:
            return jsonify({
                'success': False,
                'error': 'Todo not found',
                'code': 'TODO_NOT_FOUND'
            }), 404
        
        data = request.get_json()
        if not data or 'title' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required title field',
                'code': 'MISSING_TITLE'
            }), 400
        
        todo.title = data['title']
        todo.description = data.get('description', todo.description)
        todo.completed = data.get('completed', todo.completed)
        todo.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': {
                'id': todo.id,
                'title': todo.title,
                'description': todo.description,
                'completed': todo.completed,
                'created_at': todo.created_at.isoformat(),
                'updated_at': todo.updated_at.isoformat(),
                'user': {
                    'id': todo.user.id,
                    'username': todo.user.username
                }
            },
            'message': 'Todo updated successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_SERVER_ERROR'
        }), 500

@main_bp.route('/todos/<int:id>', methods=['DELETE'])
def delete_todo(id):
    try:
        user_id, error = get_user_id()
        if error:
            return jsonify(error), 400
        
        todo = Todo.query.filter_by(id=id, user_id=user_id).first()
        if not todo:
            return jsonify({
                'success': False,
                'error': 'Todo not found',
                'code': 'TODO_NOT_FOUND'
            }), 404
        
        db.session.delete(todo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Todo deleted successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_SERVER_ERROR'
        }), 500