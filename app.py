from flask import Flask, request, jsonify,send_from_directory,render_template
import os
import uuid
import cv2
import time
from flask_migrate import Migrate
from my_functions import object_detection, inside_box, img_classify  # Ensure these are properly defined
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
app = Flask(__name__)


# Add this line after initializing your Flask app
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Replace with your preferred database URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
# migrate = Migrate(app, db)
# Define the User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Primary Key
    name = db.Column(db.String(100), nullable=False)  # Name of the user
    email = db.Column(db.String(120), unique=True, nullable=False)  # Email (unique)
    phone = db.Column(db.String(15), unique=True, nullable=False)  # Phone number (unique)
    password = db.Column(db.String(255), nullable=False)  # Password (hashed)

    def __repr__(self):
        return f'<User {self.name}>'

# Create the database tables
# with app.app_context():
#     db.drop_all()
#     db.create_all()

# Define the Records table
class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='records')

# Define the Videos table
class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    context = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    record_id = db.Column(db.Integer, db.ForeignKey('record.id'), nullable=False)
    record = db.relationship('Record', backref='videos')
    url = db.Column(db.String(500), nullable=False)

# Define the Riders table
class Rider(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    video = db.relationship('Video', backref='riders')

# Define the Number Plate table
class NumberPlate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    video = db.relationship('Video', backref='number_plates')

# Create the tables
with app.app_context():
    db.create_all()
class UserView(ModelView):
    def create_form(self, obj=None):
        form = super().create_form(obj)
        return form

    def edit_form(self, obj=None):
        form = super().edit_form(obj)
        return form

    def on_model_change(self, form, model, is_created):
        # Ensure all fields follow the expected formats
        if not model.phone.isdigit() or len(model.phone) != 10:
            raise ValueError("Phone number must be exactly 10 digits.")
        
        # Hash the password before saving
        if is_created or form.password.data != model.password:
            model.password = generate_password_hash(form.password.data)
        
        super().on_model_change(form, model, is_created)

# Set up Flask-Admin
class RecordView(ModelView):
    column_list = ['id', 'user.name', 'date']
    form_columns = ['user', 'date']

class VideoView(ModelView):
    column_list = ['id', 'context', 'uploaded_at', 'record.id', 'url']
    form_columns = ['context', 'record', 'url']

class RiderView(ModelView):
    column_list = ['id', 'filename', 'video.context', 'url']
    form_columns = ['filename', 'video', 'url']

class NumberPlateView(ModelView):
    column_list = ['id', 'filename', 'video.context', 'url']
    form_columns = ['filename', 'video', 'url']

# Set up Flask-Admin
admin = Admin(app, name='Admin Panel', template_mode='bootstrap4')
admin.add_view(UserView(User, db.session))
admin.add_view(RecordView(Record, db.session))
admin.add_view(VideoView(Video, db.session))
admin.add_view(RiderView(Rider, db.session))
admin.add_view(NumberPlateView(NumberPlate, db.session))

UPLOAD_FOLDER = 'uploads'
RIDERS_FOLDER = 'riders_pictures'
PLATES_FOLDER = 'number_plates'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RIDERS_FOLDER']=RIDERS_FOLDER
app.config['PLATES_FOLDER']=PLATES_FOLDER

# Ensure necessary directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RIDERS_FOLDER, exist_ok=True)
os.makedirs(PLATES_FOLDER, exist_ok=True)


from werkzeug.security import generate_password_hash

@app.route('/')
def home():
    return render_template('index.html')  # Renders index.html from the "templates" folder

@app.route('/riders_pictures/<filename>')
def get_image(filename):
    return send_from_directory(app.config['RIDERS_FOLDER'], filename)

@app.route('/number_plates/<filename>')
def get_number(filename):
    return send_from_directory(app.config['PLATES_FOLDER'], filename)

@app.route('/uploads/<filename>')
def get_videos(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)




@app.route('/add_user', methods=['POST'])
def add_user():
    try:
        # Get JSON data from the request
        data = request.get_json()

        # Validate input data
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        password = data.get('password')

        if not name or not email or not phone or not password:
            return jsonify({"error": "Missing data"}), 400

        # Check if the email or phone already exists
        existing_user = User.query.filter((User.email == email) | (User.phone == phone)).first()
        if existing_user:
            return jsonify({"error": "Email or phone already exists"}), 400

        # Hash the password for security
        hashed_password = generate_password_hash(password)

        # Create a new User object with the hashed password
        new_user = User(name=name, email=email, phone=phone, password=hashed_password)

        # Add user to the database
        db.session.add(new_user)
        db.session.commit()

        # Return a success message with the user's details
        return jsonify({
            "message": "User added successfully",
            "user": {
                "id": new_user.id,
                "name": new_user.name,
                "email": new_user.email,
                "phone": new_user.phone
            }
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/login_user', methods=['POST'])
def login_user():
    # print(request.json)
    phone = request.form.get('phone')
    password = request.form.get('password')
    # data = request.json
    # phone = data.get('phone')
    # password = data.get('password')
    print(phone,password)
    if not phone or not password:
        return jsonify({'error': 'Phone number and password are required'}), 400

    # Find user by phone
    user = User.query.filter_by(phone=phone).first()

    if not user:
        return jsonify({ 'status':'faild','error': 'User not found'}), 200

    # Check password
    if not check_password_hash(user.password, password):
        return jsonify({'status':'faild','error': 'Invalid password'}), 200

    return jsonify({
        'status':'success',
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'phone': user.phone
        }
    }), 200



@app.route('/upload', methods=['POST'])
def upload_video():
    try:
        data = request.form
        user_id = data.get('user_id')
        context = data.get('context')  # Filename as context

        if not user_id or not context:
            return jsonify({"error": "Missing user_id or context"}), 400

        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400

        video = request.files['video']
        if video.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # Generate a unique ID and save the file
        unique_id = str(uuid.uuid4())
        file_extension = os.path.splitext(video.filename)[1]
        filename = f"{unique_id}{file_extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        video.save(filepath)
        
        source = filepath 
        frame_size = (800, 480)
        # Process the video
        cap = cv2.VideoCapture(source)
        rider_image_paths = []
        plate_image_paths = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.resize(frame, frame_size) 
            original_frame = frame.copy()
            frame, results = object_detection(frame)
            
            rider_list = []
            head_list = []
            number_list = []

            for result in results:
                x1, y1, x2, y2, cnf, clas = result
                if clas == 0:
                    rider_list.append(result)
                elif clas == 1:
                    head_list.append(result)
                elif clas == 2:
                    number_list.append(result)

            for rdr in rider_list:
                timestamp = str(time.time())
                x1r, y1r, x2r, y2r, _, _ = rdr
                for hd in head_list:
                    x1h, y1h, x2h, y2h, _, _ = hd
                    if inside_box([x1r, y1r, x2r, y2r], [x1h, y1h, x2h, y2h]):
                        helmet_present = img_classify(original_frame[y1h:y2h, x1h:x2h])
                        if helmet_present[0] == False:
                            rider_img_filename = f'{timestamp}.jpg'
                            rider_img_path = os.path.join(RIDERS_FOLDER, rider_img_filename)
                            cv2.imwrite(rider_img_path, original_frame[y1r:y2r, x1r:x2r])
                            rider_image_paths.append(rider_img_path)

                            for num in number_list:
                                x1n, y1n, x2n, y2n, confn, _ = num
                                if inside_box([x1r, y1r, x2r, y2r], [x1n, y1n, x2n, y2n]):
                                    plate_img_filename = f'{timestamp}_{confn}.jpg'
                                    plate_img_path = os.path.join(PLATES_FOLDER, plate_img_filename)
                                    cv2.imwrite(plate_img_path, original_frame[y1n:y2n, x1n:x2n])
                                    plate_image_paths.append(plate_img_path)

        cap.release()

        # Get today's date
        # Get today's date (without time)
        today = datetime.utcnow().date()

        # Fetch existing record for the same user and date
        record = Record.query.filter(
            Record.user_id == user_id,
            db.func.date(Record.date) == today
        ).first()

        # If no record exists, create one
        if not record:
            record = Record(user_id=user_id, date=datetime.utcnow())  # Ensure UTC timestamp
            db.session.add(record)
            db.session.commit()


        # Add video entry
        video_entry = Video(context=context, uploaded_at=datetime.utcnow(), record_id=record.id, url=filepath)
        db.session.add(video_entry)
        db.session.commit()
        video_id = video_entry.id

        # Add detected riders to database
        for rider_img_path in rider_image_paths:
            rider_filename = os.path.basename(rider_img_path)
            rider_entry = Rider(url=rider_img_path, filename=rider_filename, video_id=video_entry.id)
            db.session.add(rider_entry)
        
        # Add detected number plates to database
        for plate_img_path in plate_image_paths:
            plate_filename = os.path.basename(plate_img_path)
            plate_entry = NumberPlate(url=plate_img_path, filename=plate_filename, video_id=video_entry.id)
            db.session.add(plate_entry)

        db.session.commit()

        return jsonify({
            "message": "Video uploaded and processed successfully",
            "video_id": video_id,
            "unique_id": unique_id,
            "file_path": filepath,
            "rider_images": rider_image_paths,
            "plate_images": plate_image_paths
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_records', methods=['POST'])
def get_records():
    try:
        user_id = request.form.get('user_id')
       
        from_date_str = request.form.get('from_date', None)  # Optional date filter

        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        # Convert from_date string to datetime object
        if from_date_str:
            try:
                from_date = datetime.strptime(from_date_str, "%Y-%m-%d")
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
        else:
            from_date = None  # No date filter applied

        # Query records for the user, optionally filtering by date
        query = Record.query.filter_by(user_id=user_id)
        if from_date:
            query = query.filter(Record.date >= from_date)

        records = query.all()

        if not records:
            return jsonify({ 'status':'empty',"message": "No records found"}), 200

        # Prepare response with formatted date
        records_data = [
            {"record_id": record.id, "date": record.date.strftime("%d %B %Y")}
            for record in records
        ]

        return jsonify({ 'status':'success',"records": records_data}), 200

    except Exception as e:
        return jsonify({ 'status':'error',"error": str(e)}), 500

@app.route('/get_videos_by_record', methods=['POST'])
def get_videos_by_record():
    try:
        record_id = request.form.get('record_id')
        

        if not record_id:
            return jsonify({"error": "Missing record_id"}), 400

        # Query the videos based on the record_id
        videos = Video.query.filter_by(record_id=record_id).all()

        if not videos:
            return jsonify({'status':'empty',"error": "No videos found for this record"}), 200

        # Prepare the video data with the calculated time ago
        videos_data = [
            {
                "video_id": video.id,
                "context": video.context,
                "uploaded_at": time_ago(video.uploaded_at),  # Convert uploaded_at to time ago
                "url": video.url
            }
            for video in videos
        ]

        return jsonify({'status':'success',"videos": videos_data}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
def time_ago(uploaded_at):
    now = datetime.utcnow()
    diff = now - uploaded_at

    # Get the difference in seconds
    diff_in_seconds = diff.total_seconds()

    # Calculate how many days, hours, and minutes
    if diff_in_seconds < 60:
        return "Uploaded just now"
    elif diff_in_seconds < 3600:
        minutes = int(diff_in_seconds // 60)
        return f"Uploaded {minutes} minute{'s' if minutes > 1 else ''} ago"
    elif diff_in_seconds < 86400:
        hours = int(diff_in_seconds // 3600)
        return f"Uploaded {hours} hour{'s' if hours > 1 else ''} ago"
    elif diff_in_seconds < 2592000:
        days = int(diff_in_seconds // 86400)
        return f"Uploaded {days} day{'s' if days > 1 else ''} ago"
    else:
        months = int(diff_in_seconds // 2592000)
        return f"Uploaded {months} month{'s' if months > 1 else ''} ago"


@app.route('/get_riders', methods=['POST'])
def get_riders():
    try:
        video_id = request.form.get('video_id')
 
    

        if not video_id:
            return jsonify({"error": "Missing video_id"}), 400

        # Query riders based on video_id
        riders = Rider.query.filter_by(video_id=video_id).all()

        if not riders:
            return jsonify({'status':'empty',"error": "No riders found for this video"}), 200

        # Prepare rider data
        riders_data = [
            {
                "rider_id": rider.id,
                "filename": rider.filename,
                "url": rider.url
            }
            for rider in riders
        ]

        return jsonify({'status':'success',"riders": riders_data}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_number_plates', methods=['POST'])
def get_number_plates():
    try:
        video_id = request.form.get('video_id')
 
    

        if not video_id:
            return jsonify({"error": "Missing video_id"}), 400

        # Query number plates based on video_id
        plates = NumberPlate.query.filter_by(video_id=video_id).all()

        if not plates:
            return jsonify({'status':'empty',"error": "No number plates found for this video"}), 200

        # Prepare number plate data
        plates_data = [
            {
                "plate_id": plate.id,
                "filename": plate.filename,
                "url": plate.url
            }
            for plate in plates
        ]

        return jsonify({'status':'success',"number_plates": plates_data}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000)
