from flask import Flask, render_template, request, redirect, url_for
import os
import datetime
import pymongo
from bson.objectid import ObjectId
from dotenv import load_dotenv
from passlib.hash import pbkdf2_sha256
import flask_login
load_dotenv()

MONGO_URI = os.environ.get('MONGO_URI')
DB_NAME = "animal_shelter"

# Creates a mongo client
client = pymongo.MongoClient(MONGO_URI)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") # set the secret key

# Creates a login manager
login_manager = flask_login.LoginManager()  # this relatd to OOP
login_manager.init_app(app) # this login manager is created to manage logins for our flask app


# use back the user class from flask_login
class User(flask_login.UserMixin):
    pass


def encrypt_password(plaintext):
    return pbkdf2_sha256.hash(plaintext)


def verify_password(plaintext, encrypted):
    return pbkdf2_sha256.verify(plaintext, encrypted)


# the user_loader executes automatically whenever the browser sends a request to our flask app
# it will grab the email or username from the session and try to see if it exists or not
@login_manager.user_loader
def user_loader(email):
    user_data = client[DB_NAME].users.find_one({
        "email":email
    })

    # Create a User object
    logged_in_user = User() # create an object from the User class by using the name of the class like a function
    logged_in_user.id = user_data['email']
    return logged_in_user


@app.route('/show_animals')
def show_animals():
    all_animals = client[DB_NAME].animals.find()
    return render_template('show_animals.template.html', results=all_animals)


@app.route('/create_animal')
def show_create_animal_form():
    return render_template('create_animal.template.html')


@app.route('/create_animal', methods=['POST'])
def process_create_animal():
    # mongo shell uses insert, pymongo uses insert_one
    client.animal_shelter.animals.insert_one({
        "name": request.form.get("animal_name"),
        "breed": request.form.get("animal_breed"),
        "created_by": flask_login.current_user.id
    })
    return "added"


@app.route('/edit_animal/<animal_id>')
def show_edit_animal(animal_id):
    # we use find_one() when we just want one result
    animal = client[DB_NAME].animals.find_one({
        "_id": ObjectId(animal_id)
    })

    """ 
    BIG REMIDNER -- Not all animals have checkups, so you must check 
    if it exists first
    if animal.checkups:
        # if checkups then do something
    """

    return render_template('edit_animal.template.html', animal=animal)


@app.route('/edit_animal/<animal_id>', methods=["POST"])
def process_edit_animal(animal_id):

    client[DB_NAME].animals.update_one({
        "_id": ObjectId(animal_id)
    }, {
        "$set":{
            "name": request.form.get('animal_name'),
            "breed": request.form.get("animal_breed")
        }
    })
    return redirect(url_for("show_animals"))


@app.route('/checkups/<animal_id>')
def show_checkups_for_animal(animal_id):

    vets = client[DB_NAME].vets.find()

    animal = client[DB_NAME].animals.find_one({
        "_id": ObjectId(animal_id),
    }, {
        'name': 1, 'checkups': 1
    })

    return render_template('show_checkups.template.html',
                           animal=animal,
                           vets=vets)


@app.route('/checkups/<animal_id>', methods=["POST"])
def add_checkups(animal_id):

    vet = client[DB_NAME].vets.find_one({
        "_id": ObjectId(request.form.get('vet'))
    })
    animal = client[DB_NAME].animals.update({
        "_id": ObjectId(animal_id)
    }, {
        "$push": {
            'checkups': {
                "checkup_id": ObjectId(),
                "vet_id": vet['_id'],
                "vet": vet['name'],
                "diagnosis": request.form.get("diagnosis"),
                "date": datetime.datetime.strptime(request.form.get('date'), "%Y-%m-%d")
            }
        }
    })
    return redirect(url_for('show_checkups_for_animal', animal_id=animal_id))

@app.route("/delete_checkups/<animal_id>/<checkup_id>")
def delete_checkup(animal_id, checkup_id):
    client[DB_NAME].animals.update({
        "_id": ObjectId(animal_id)
    }, {
        '$pull': {
            'checkups': {
                "checkup_id": ObjectId(checkup_id)
            }
        }
    })
    return redirect(url_for('show_checkups_for_animal', animal_id=animal_id))

@app.route("/delete_animal/<animal_id>")
def delete_animal(animal_id):
    client[DB_NAME].animals.remove({
        "_id": ObjectId(animal_id)
    })
    return redirect(url_for('show_animals'))


@app.route("/edit_checkup/<checkup_id>")
def edit_checkup(checkup_id):

    # grab the vets
    vets = client[DB_NAME].vets.find()

    # retrieve the checkup
    checkup = client[DB_NAME].animals.find_one({
        'checkups.checkup_id': ObjectId(checkup_id)
    }, {
        'checkups': {'$elemMatch': {
            'checkup_id': ObjectId(checkup_id)
        }}
    })['checkups'][0]

    return render_template('edit_checkup.template.html',
                           checkup=checkup,
                           vets=vets)


@app.route('/edit_checkup/<checkup_id>', methods=["POST"])
def process_edit_checkup(checkup_id):

    vet = client[DB_NAME].vets.find_one({
        '_id': ObjectId(request.form.get('vet'))
    })

    animal = client[DB_NAME].animals.find_one({
          "checkups.checkup_id": ObjectId(checkup_id)
    })

    client[DB_NAME].animals.update({
        "checkups.checkup_id": ObjectId(checkup_id)
    }, {
        '$set': {
            'checkups.$.vet_id': request.form.get('vet_id'),
            'checkups.$.vet': vet['name'],
            'checkups.$.diagnosis': request.form.get('diagnosis'),
            'checkups.$.date': datetime.datetime.strptime(request.form.get('date'), "%Y-%m-%d")
        }
    })
    return redirect(url_for('show_checkups_for_animal', animal_id=animal['_id']))


@app.route('/login')
def login():
    return render_template('login.template.html')


@app.route('/login', methods=["POST"])
def process_login():
    email = request.form.get('email')
    password =request.form.get('password')

    # get the user by the provided email
    user_data = client[DB_NAME].users.find_one({
        "email":email
    })

    # if the user exists
    if user_data and verify_password(password, user_data['password']):
        logged_in_user = User()
        logged_in_user.id = user_data['email']
        flask_login.login_user(logged_in_user)
        return "Logged in success"
    else:
        return "Logged in failed"


@app.route('/signup')
def signup():
    return render_template('signup.template.html')


@app.route('/signup', methods=['POST'])
def process_signup():
    email = request.form.get('email')
    password = request.form.get('password')
    name = request.form.get('name')

    # make sure that the email is unique
    existing_user = client[DB_NAME]['users'].find_one({
        "email":email
    })

    if existing_user:
        return "Email is already in use"

    client[DB_NAME]['users'].insert_one({
        "name": name,
        "password": encrypt_password(password),
        "email": email
    })
    return "User createed"


@app.route('/protected')
@flask_login.login_required
def private_sections():
    return "Only logged in user can see this. You are " + flask_login.current_user.id


@app.route('/logout')
def logout():
    flask_login.logout_user()
    return "Logged out"


# "magic code" -- boilerplate
if __name__ == '__main__':
    app.run(host=os.environ.get('IP'),
            port=int(os.environ.get('PORT')),
            debug=True)
