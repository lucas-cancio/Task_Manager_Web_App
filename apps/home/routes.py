# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from apps.home import blueprint
from flask import render_template, request, redirect, url_for
from flask_login import login_required, current_user
from jinja2 import TemplateNotFound
from apps.authentication.models import Users, Task
from sqlalchemy import func
from apps import db
import datetime
import requests

task_hierarchy = []

@blueprint.route('/index')
@login_required
def index():

    user = Users.find_by_username(current_user.username)

    tasks = Task.query.filter_by(user=user).all()
    task_hierarchy = create_hierarchy(tasks)

    return render_template('home/index.html', segment='index', task_hierarchy=task_hierarchy)

def create_task_hierarchy(task):
    print("do nothing")


@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment

    except:
        return None



@blueprint.route('/add', methods=['POST'])
def add():

    user = Users.find_by_username(current_user.username)

    task_title = request.form.get('task_title')
    task_description = request.form.get('task_description')

    task_due_date_time = request.form.get('due_date_time')
    date_processing = task_due_date_time.replace('T', '-').replace(':', '-').split('-')
    date_processing = [int(v) for v in date_processing]
    task_due_date_time = datetime.datetime(*date_processing)

    parent_task = request.form.get('parent_task')
    
    new_task = Task(title=task_title, description=task_description, due_date=task_due_date_time, user=user, parent_item_id=parent_task)
    db.session.add(new_task)
    db.session.commit()

    update_task_progress_percent(parent_task)

    return redirect(url_for('home_blueprint.index'))


@login_required
@blueprint.route('/delete/<int:task_id>')
def delete(task_id):

    user = Users.find_by_username(current_user.username)

    task = Task.query.filter_by(id=task_id, user=user).first()
    parent_task_id = task.parent_item_id

    delete_task_and_subtasks(task_id)

    update_task_progress_percent(parent_task_id)


    return redirect(url_for('home_blueprint.index'))

def delete_task_and_subtasks(task_id):
    # Get the task and its subtasks
    task = Task.query.get(task_id)
    subtasks = Task.query.filter(Task.parent_item_id == task_id).all()

    # Delete subtasks first
    for subtask in subtasks:
        delete_task_and_subtasks(subtask.id)

    # Delete the current task
    db.session.delete(task)
    db.session.commit()


@login_required
@blueprint.route('/edit', methods=['POST'])
def edit_item():
  
    field = request.form.get("field")
    value = request.form.get("value")
    task_id = request.form.get("id")
    
    task = Task.query.filter_by(id=task_id).first()

    if (field == "title"):
        task.title = value

    elif (field == "description"):
        task.description = value

    elif (field == "due_date"):
        task.due_date = value

    elif (field == "progress"):
        task.progress = value

        task.progress_percent = 0.00 if value == "Not Started" else 100.00

        db.session.commit()

        print("task #" + str(task.id) +  "progress: " + str(task.progress) + str(task.progress_percent) + "%")

        # dictionary mapping task ID to new percent completed
        res = {}

        # update progress_percent of parent task
        if task.parent_item_id:
            update_task_progress_percent(id=task.parent_item_id, id_to_progress_percent=res)

        return res
        
    db.session.commit()

    return None

def update_task_progress_percent(id, id_to_progress_percent = {}):
    
    task_id = id
    task = Task.query.filter_by(id=task_id).first()

    total_child_task_completion = db.session.query(func.sum(Task.progress_percent)).filter(Task.parent_item_id==task.id).scalar()
    num_child_tasks = db.session.query(func.count()).filter(Task.parent_item_id==task.id).scalar()
    percent_complete = total_child_task_completion / num_child_tasks
    
    task.progress_percent = percent_complete

    id_to_progress_percent[task_id] = percent_complete

    if percent_complete == 100:
        task.progress = "Completed"
    elif percent_complete == 0:
        task.progress = "Not Started"

    db.session.commit()

    # update progress_percent of parent task
    if task.parent_item_id:
        update_task_progress_percent(id=task.parent_item_id, id_to_progress_percent=id_to_progress_percent) 






def create_hierarchy(tasks):
    # Map parents to children
    parent_to_children = {}

    for task in tasks:
        task_id, parent_id = task.id, task.parent_item_id

        if parent_id not in parent_to_children:
            parent_to_children[parent_id] = []
        
        parent_to_children[parent_id].append({'task': task, 'children': []})

    # Construct the hierarchy
    root_nodes = parent_to_children[None] # root nodes have a parent of None
    task_hierarchy.clear()

    for root_node in root_nodes:
        build_hierarchy(root_node, parent_to_children)
        task_hierarchy.append(root_node)

    return task_hierarchy

def build_hierarchy(node, parent_to_children):
    task_id = node['task'].id
    node['children'] = parent_to_children.get(task_id)

    if node['children'] != None:
        for child_task in node['children']:
            build_hierarchy(child_task, parent_to_children)
