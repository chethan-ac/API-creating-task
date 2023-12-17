from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '12345'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    f_name = db.Column(db.String(50), nullable=False)
    l_name = db.Column(db.String(50), nullable=False)
    email_id = db.Column(db.String(100), unique=True, nullable=False)
    phone_number = db.Column(db.String(15), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

    def as_dict(self):
        return {
            'id': self.id,
            'f_name': self.f_name,
            'l_name': self.l_name,
            'email_id': self.email_id,
            'phone_number': self.phone_number,
            'address': self.address,
            'created_date': self.created_date.strftime('%Y-%m-%d %H:%M:%S')
        }

@app.route('/oauth/token', methods=['POST'])
def generate_token():
    # Simplified token generation (no expiration logic for this example)
    access_token = 'abc123'
    return jsonify({'access_token': access_token})

@app.route('/insert_user', methods=['POST'])
def insert_user():
    try:
        data = request.get_json()
        new_user = User(
            f_name=data['f_name'],
            l_name=data['l_name'],
            email_id=data['email_id'],
            phone_number=data['phone_number'],
            address=data['address']
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify(new_user.as_dict()), 201
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"error": "Email ID already exists"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/list_users', methods=['GET'])
def list_users():
    users = User.query.all()
    users_list = [user.as_dict() for user in users]
    return jsonify(users_list)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)