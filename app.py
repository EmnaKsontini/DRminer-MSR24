from flask import Flask, render_template, request, jsonify
from crud import ProjectService
from db import db
from final import process_github_repo
from models import Project
from flask_migrate import Migrate
import logging
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test3.db' # you can change the path as per your needs
db.init_app(app)
migrate = Migrate(app, db)
@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')


@app.route('/create_project', methods=['POST'])
def create_project():
    # Assuming `project_data` is the dictionary containing your project data
    project_data = request.get_json()

    # Create and add new project to the database
    new_project = Project(**project_data)
    db.session.add(new_project)
    db.session.commit()

    # Convert the project to a dictionary so it can be returned as JSON
    # Make sure that this dictionary includes the 'id' of the created project
    project_dict = {
        'id': new_project.id,
        'repo_path': new_project.repo_path,
        'commit_hash': new_project.commit_hash,
        # 'dockerfile_path': new_project.dockerfile_path,
    }

    return jsonify(project_dict), 201
def validate_project_id(project_id):
    """
    Validates if the provided project ID is valid and exists in the database.
    """
    project = Project.query.get(project_id)
    if not project:
        abort(404, description='Project not found')
    return project

@app.route('/get_project', methods=['POST'])
def get_project():
    try:
        project_id = request.json.get('project_id')
        project = validate_project_id(project_id)
        if project is None:
            return jsonify({'error': 'Project not found'}), 404
        project_dict = {
            'id': project.id,
            'repo_path': project.repo_path,
            'commit_hash': project.commit_hash,
            #'dockerfile_path': project.dockerfile_path,
        }
        return jsonify(project_dict), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_projects', methods=['GET'])
def get_projects():
    return jsonify(ProjectService().get_projects())

@app.route('/get_projects_data', methods=['POST'])
def get_projects_data():
    project_ids = request.get_json().get('projectIds')
    logging.info(f"Received projectIds: {project_ids}")

    refactoring_counts = {}

    for project_id in project_ids:
        project = validate_project_id(project_id)
        output = process_github_repo(project.repo_path, project.commit_hash)
        
        # Iterate through each Dockerfile's refactoring information
        for dockerfile in output:
            refactorings = dockerfile[1]  # The second element is the refactoring info

            # If the refactoring info is not None, process it
            if refactorings:
                for refactoring_type, tasks in refactorings.items():
                    # If the refactoring type is not None, add or increment its count
                    if tasks:
                        if refactoring_type not in refactoring_counts:
                            refactoring_counts[refactoring_type] = 0
                        refactoring_counts[refactoring_type] += len(tasks)

    logging.info(f"Refactoring counts: {refactoring_counts}")
    return jsonify({
            'refactoring_counts': refactoring_counts,
            # Include other data if necessary
        })



@app.route('/get_refactorings', methods=['POST'])
def get_refactorings_route():
    try:
        project_id = request.json.get('project_id')
        refactorings = ProjectService().get_refactorings_for_project(project_id)
        
        return jsonify(refactorings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect_refactorings', methods=['POST'])
def detect_refactorings_route():
    try:
        # Extract data from request
        repo_path = request.json.get('repo_path')
        commit_hash = request.json.get('commit_hash')
        # dockerfile_path = request.json.get('dockerfile_path')
        # temp_repo_path = "C:/Users/Miss_A/Desktop/website2/1/temp_repo"
        # dockerfile_path = temp_repo_path + dockerfile_path

        # Call your function
        output = process_github_repo(repo_path, commit_hash)
        refactoring_counts = {}

        # Iterate through each Dockerfile's refactoring information
        for dockerfile in output:
            refactorings = dockerfile[1]  # The second element is the refactoring info

            # If the refactoring info is not None, process it
            if refactorings:
                for refactoring_type, tasks in refactorings.items():
                    # If the refactoring type is not None, add or increment its count
                    if tasks:
                        if refactoring_type not in refactoring_counts:
                            refactoring_counts[refactoring_type] = 0
                        refactoring_counts[refactoring_type] += len(tasks)

        

        # Store the refactorings
        #project_service = ProjectService()  <-- removed this line
        #project = project_service.get_project_by_repo_path(repo_path)  <-- removed this line
        #if project is not None:
        #    project_service.detect_and_store_refactorings(project.id, refactoring_counts)  <-- removed this line
        logging.info(f"Refactoring counts: {refactoring_counts}")
        # Include the counts in the response
        return jsonify({
            'refactoring_counts': refactoring_counts,
            # Include other data if necessary
        })

    except Exception as e: 
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
