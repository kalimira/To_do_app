from functools import wraps
from flask import Flask, request, Response, g, redirect, url_for, session, jsonify
import mysql.connector
import json
from datetime import timedelta
from flask_cors import CORS
import re

app = Flask(__name__)
app.secret_key = 'super secret key'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['JSON_SORT_KEYS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] =  timedelta(minutes=10)
CORS(app)

@app.route('/')
def hello_world():
    print(session)
    if 'username' in session:
        username = session['username']
        return jsonify({'message' : 'You are already logged in', 'username' : username})
    else:
        resp = jsonify({'message' : 'Unauthorized'})
        resp.status_code = 401
        return resp

@app.route('/login', methods=['POST'])
def login():
    conn = None;
    cursor = None;
    _json = request.json
    try:
        _json = request.json
        _username = _json['username']
        _password = _json['password']

        if _username and _password:
            conn = connect_to_db()
            cursor = conn.cursor()
            sql = "SELECT * FROM profile WHERE username=%s"
            sql_where = (_username,)
            cursor.execute(sql, sql_where)
            row = cursor.fetchone()
            if row:
                password = row[2]
                if password == _password:
                    user = _username
                    session['username'] = user
                    message = 'You are logged in successfully' 
                    return jsonify({'message' : message})
                else:
                    message = 'Bad Request - invalid password'
                    resp = jsonify({'message' : message})
                    resp.status_code = 400
                    return resp
            else:
                message = 'You have not profile'
                resp = jsonify({'message' : message})
                resp.status_code = 400
                return resp
        else:
            message = 'Bad Request - invalid credentials'
            resp = jsonify({'message' : message})
            resp.status_code = 400
            return resp
        cursor.close()
    except Exception as e:
        return jsonify({'message' : e})

@app.route('/projects', methods=['GET', 'POST', 'DELETE', 'PATCH'])
def projects():
    _json = request.get_json()
    conn = connect_to_db()
    cursor = conn.cursor()
    if request.method == 'GET':
        visit_user = _json['visit']
        result = show_projects(visit_user, cursor)
        return jsonify({'projects': result})
    else:
        if 'username' in session:
            user = session['username']
            if request.method == 'POST':
                result = insert_project(user, _json, conn)
                return jsonify({'message': result})
            if request.method == 'DELETE':
                result = delete_project(user, _json, conn)
                return jsonify({'message': result})
            if request.method == 'PATCH':
                result = change_project(user, _json, conn)
                return jsonify({'message': result})
        else:
            error = 'please login to do this operations'
            return jsonify({'error': error})

@app.route('/projects/tasks', methods=['GET', 'POST', 'DELETE', 'PATCH'])
def tasks():
    _json = request.get_json()
    conn = connect_to_db()
    cursor = conn.cursor()
    if request.method == 'GET':
        visit_user = _json['visit']
        visit_project = _json['project']
        rows = show_tasks(visit_user, visit_project, cursor)
        return jsonify({'tasks in project' : rows})
    else:
        if 'username' in session:
            user = session['username']
            if request.method == 'POST':
                result = insert_tasks(user, _json, conn)
                return jsonify({'message': result})
            if request.method == 'DELETE':
                result = delete_tasks(user, _json, conn)
                return jsonify({'message': result})
            if request.method == 'PATCH':
                result = change_task(user, _json, conn)
                return jsonify({'message': result})
        else:
            error =  'please login to do this operations'
            return jsonify({'error': error})

def show_projects(user, cursor):
    sql = "SELECT projects.name, projects.description FROM  projects JOIN profile ON projects.user = profile.username WHERE profile.username=%s;"
    sql_where = (user,)
    cursor.execute(sql, sql_where)
    result = []
    rows = cursor.fetchall()
    if rows:
        for index, row in enumerate(rows):
            result.append({"project": rows[index][0], "project_description":rows[index][1]}) 
    return result

def show_tasks(visit_user, visit_project, cursor):
    sql = "SELECT projects.user, projects.name, tasks.name, tasks.status FROM projects JOIN tasks ON projects.name = tasks.project WHERE projects.name=%s AND projects.user = %s"
    sql_where = (visit_project, visit_user)
    cursor.execute(sql, sql_where)
    result = []
    rows = cursor.fetchall()
    if rows:
        for index, row in enumerate(rows):
            result.append({'user': rows[index][0], 'project': rows[index][1],'task': rows[index][2], 'status': rows[index][3]}) 
    return result

def insert_project(user, _json, conn):
    sql = "INSERT INTO projects (user, name, description) VALUES (%s, %s, %s)"
    project = _json['project']
    description = _json['description']
    val = (user, project, description)
    cursor = conn.cursor()
    cursor.execute(sql, val)
    conn.commit()
    message = "you have added a project"
    return message

def insert_tasks(user, _json, conn):
    cursor = conn.cursor()
    result = is_there_project(user, _json, cursor)
    if result:
        return result
    sql = "INSERT INTO tasks (name, status, project) VALUES (%s, %s, %s)"
    task = _json['task']
    status = _json['status']
    project = _json['project']
    val = (task, status, project)
    cursor.execute(sql, val)
    conn.commit()
    message = "you have added a task"
    return message

def delete_project(user, _json, conn):
    cursor = conn.cursor()
    result = is_there_project(user, _json, cursor)
    if result:
        return result
    sql = "DELETE FROM projects WHERE user=%s AND name=%s"
    project = _json['project']
    sql_where = (user, project)
    cursor.execute(sql, sql_where)
    conn.commit()
    message = "you have deleted a project"
    return message

def delete_tasks(user, _json, conn):
    cursor = conn.cursor()
    result = is_there_task(user, _json, cursor)
    if result:
        return result
    sql = "DELETE tasks FROM tasks JOIN projects ON tasks.project=projects.name WHERE projects.user=%s AND tasks.name=%s AND tasks.project=%s"
    task = _json['task']
    project = _json['project']
    sql_where = (user, task, project)
    cursor.execute(sql, sql_where)
    conn.commit()
    message = "you have deleted a task"
    return message

def change_project(user, _json, conn):
    cursor = conn.cursor()
    result = is_there_project(user, _json, cursor)
    if result:
        return result
    tag = list(_json.keys())[-1]
    rx = re.search(r'(.*?)_', tag).group(0)
    column = tag.split(rx,1)[1]
    if column == 'name':
        sql = "UPDATE projects SET name=%s WHERE name=%s AND user=%s"
    elif column == 'description':
        sql = "UPDATE projects SET description=%s WHERE name=%s AND user=%s"
    else:
        message = "please use correct key for the update"
        return message
    update = _json[tag]
    project = _json['project']
    sql_where = (update, project, user)
    cursor.execute(sql, sql_where)
    conn.commit()
    message = "you have changed the project"
    return message
    

def change_task(user, _json, conn):
    cursor = conn.cursor()
    result = is_there_task(user, _json, cursor)
    if result:
        return result
    tag = list(_json.keys())[-1]
    rx = re.search(r'(.*?)_', tag).group(0)
    column = tag.split(rx,1)[1]
    if column == 'status':
        sql = "UPDATE tasks JOIN projects ON tasks.project=projects.name SET tasks.status=%s WHERE tasks.name=%s AND projects.user=%s AND tasks.project=%s"
    elif column == 'project':
        sql = "UPDATE tasks JOIN projects ON tasks.project=projects.name SET tasks.project=%s WHERE tasks.name=%s AND projects.user=%s AND tasks.project=%s"
    elif column == 'name':
        sql = "UPDATE tasks JOIN projects ON tasks.project=projects.name SET tasks.name=%s WHERE tasks.name=%s AND projects.user=%s AND tasks.project=%s"
    else:
        message = "please use correct key for the update"
        return message
    update = _json[tag]
    task = _json['task']
    project = _json['project']
    sql_where = (update, task, user, project)
    cursor.execute(sql, sql_where)
    conn.commit()
    message = "you have changed the task"
    return message

def is_there_project(user, _json, cursor):
    sql = "SELECT name FROM projects WHERE user=%s AND name=%s"
    project = _json['project']
    sql_where = (user, project)
    cursor.execute(sql, sql_where)
    rows = cursor.fetchall()
    if not rows:
        message = "this project don't exist"
        return message
    return

def is_there_task(user, _json, cursor):
    sql = "SELECT tasks.name FROM tasks JOIN projects ON tasks.project=projects.name WHERE tasks.project=%s AND tasks.name=%s AND projects.user=%s"
    project = _json['project']
    task = task = _json['task']
    print('yes')
    sql_where = ( project, task, user)
    cursor.execute(sql, sql_where)
    rows = cursor.fetchall()
    print(rows)
    if not rows:
        message = "this task don't exist"
        return message
    return

@app.route('/signup', methods=['POST'])
def sign_up():
    req_data = request.get_json()
    profile = {}
    profile["username"] = req_data["username"]
    profile["password"] = req_data["password"]
    profile["name"] = req_data["name"]
    profile["age"] = req_data["age"]
    profile["university"] = req_data["university"]
    profile["work"] = req_data["work"]

    res_data = add_profile(profile)
    if res_data is None:
        message = 'Profile not added'
        return jsonify({'message' : message})

    response = jsonify({'message': res_data}) 
    return response

def connect_to_db():
    conn = mysql.connector.connect(host="localhost",user="root",password="",database="todoapp")
    return conn

def add_profile(profile):
    conn = connect_to_db()
    cursor = conn.cursor()
    _username = profile["username"]
    sql = "SELECT * FROM profile WHERE username=%s"
    sql_where = (_username,)
    cursor.execute(sql, sql_where)
    row = cursor.fetchone()
    if row:
        message = "This username is already used."
        return message
    cursor.execute('Insert into profile(username, pass, name, age, university,work_place) values(%s,%s,%s,%s,%s,%s)',(profile["username"], profile["password"], profile["name"], profile["age"], profile["university"], profile["work"] ))
    conn.commit()
    cursor.close()
    message =  "Your account is successfully created!"
    return message

app.run(debug = True)
