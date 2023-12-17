from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_oauthlib.provider import OAuth2Provider
from datetime import datetime, timedelta
from oauthlib.oauth2 import InvalidRequestError
import secrets

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Use a proper database in production
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Suppress a warning about tracking modifications
app.config['SECRET_KEY'] = secrets.token_urlsafe(32)  # Change this to a strong secret key
app.config['OAUTH2_PROVIDER_TOKEN_EXPIRES_IN'] = 1800  # Token expires in 1800 seconds (30 minutes)
db = SQLAlchemy(app)

limiter = Limiter(
    app,
    default_limits=["5 per minute"]
)
oauth = OAuth2Provider()

# Initialize the application with OAuth provider
oauth.init_app(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    f_name = db.Column(db.String(50), nullable=False)
    l_name = db.Column(db.String(50), nullable=False)
    email_id = db.Column(db.String(100), unique=True, nullable=False)
    phone_number = db.Column(db.String(15), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

    def as_dict(self):
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class Token(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(40), nullable=False)  # Added client_id field
    user_id = db.Column(db.String(255), nullable=False)  # Added user_id field
    token_type = db.Column(db.String(40), nullable=False)  # Added token_type field
    access_token = db.Column(db.String(255), unique=True, nullable=False)
    refresh_token = db.Column(db.String(255), unique=True, nullable=True)
    expires = db.Column(db.DateTime, nullable=False)
    scopes = db.Column(db.String(255), nullable=True)  # Added scopes field

    def __init__(self, access_token, expires, client_id, user_id, token_type, refresh_token, scopes):
        self.access_token = access_token
        self.expires = expires
        self.client_id = client_id
        self.user_id = user_id
        self.token_type = token_type
        self.refresh_token = refresh_token
        self.scopes = scopes

# Authorization and Token Endpoints
@app.route('/oauth/token', methods=['POST'])
@oauth.token_handler
def access_token():
    return None

@oauth.tokensetter
def save_token(token, request, *args, **kwargs):
    expires_in = token.pop('expires_in')
    expires = datetime.utcnow() + timedelta(seconds=expires_in)

    new_token = Token(
        access_token=token['access_token'],
        refresh_token=token['refresh_token'],
        token_type=token['token_type'],
        expires=expires,
        client_id=token['client_id'],
        user_id=token['user_id'],
        scopes=token['scope']
    )

    db.session.add(new_token)
    db.session.commit()
    return new_token

@oauth.tokengetter
def load_token(access_token=None, refresh_token=None):
    if access_token:
        return Token.query.filter_by(access_token=access_token).first()
    elif refresh_token:
        return Token.query.filter_by(refresh_token=refresh_token).first()

# Handle other HTTP methods for /oauth/token
@app.route('/oauth/token', methods=['GET', 'PUT', 'DELETE', 'PATCH'])
def handle_invalid_method():
    response = jsonify({"error": "Method Not Allowed"})
    response.status_code = 405  # Method Not Allowed
    return response

# Add error handling for OAuth token endpoint
@app.errorhandler(InvalidRequestError)
def handle_invalid_request(error):
    response = jsonify({"error": "Invalid request"})
    response.status_code = 400
    return response

@oauth.clientgetter
def load_client(client_id):
    # Assuming client information is stored in a dictionary
    clients = {'client_id': {'client_id': 'client_id', 'client_secret': 'client_secret'}}
    return clients.get(client_id)

@oauth.grantgetter
def load_grant(client_id, code):
    # Assuming grant information is stored in a dictionary
    grants = {'code': {'client_id': 'client_id', 'code': 'code', 'expires': datetime.utcnow() + timedelta(hours=5,minutes=30)}}
    return grants.get(code)

@oauth.grantsetter
def save_grant(client_id, code, request, *args, **kwargs):
    expires = datetime.utcnow() + timedelta(minutes=30)
    # Storing grant information in a dictionary
    grants = {'code': {'client_id': client_id, 'code': code, 'expires': expires}}
    return grants[code]


# User Insertion Endpoint
@app.route('/insert_user', methods=['POST'])
@limiter.limit("5 per minute")
def insert_user():
    # Extract the access token from the request headers
    access_token = request.headers.get('Authorization')

    # Validate access token
    if not validate_access_token(access_token):
        return jsonify({"error": "Invalid access token"}), 401

    # Extract user details from the request JSON
    data = request.get_json()

    # Validate required parameters
    required_params = ['f_name', 'l_name', 'email_id', 'phone_number', 'address']
    if not all(param in data for param in required_params):
        return jsonify({"error": "Missing required parameters"}), 400

    # Check if email_id is unique
    if User.query.filter_by(email_id=data['email_id']).first():
        return jsonify({"error": "Email ID already exists"}), 409

    # Create a new User object with the provided details
    new_user = User(
        f_name=data['f_name'],
        l_name=data['l_name'],
        email_id=data['email_id'],
        phone_number=data['phone_number'],
        address=data['address']
    )

    # Add the new user to the database
    with app.app_context():
        db.session.add(new_user)
        db.session.commit()

    # Return the details of the newly created user
    return jsonify(new_user.as_dict()), 201

# User Listing Endpoint
@app.route('/list_users', methods=['GET'])
@limiter.limit("5 per minute")
def list_users():
    # Extract the access token from the request headers
    access_token = request.headers.get('Authorization')

    # Validate access token
    if not validate_access_token(access_token):
        return jsonify({"error": "Invalid access token"}), 401

    # Query all users from the database
    users = User.query.all()

    # Convert users to a list of dictionaries
    users_list = [user.as_dict() for user in users]

    # Return the list of users
    return jsonify(users_list), 200

def validate_access_token(token):
    stored_token = Token.query.filter_by(access_token=token).first()
    return stored_token and stored_token.expires > datetime.utcnow()


# Root URL
@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "Welcome to the API"})

if __name__ == '__main__':
    app.debug=True
    with app.app_context():
        db.create_all()
    app.run(port=7776)