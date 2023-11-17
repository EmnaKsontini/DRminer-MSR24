from models import Project
from db import db

class ProjectService:
    
    def create_project(self, repo_path, commit_hash):
        project = Project(repo_path=repo_path, commit_hash=commit_hash)
        db.session.add(project)  
        db.session.commit()
        return project.to_dict()

    def get_project(self, id):
        project = Project.query.get(id)
        return project.to_dict() if project else None

    def delete_project(self, id):
        project = Project.query.get(id)
        if project:
            db.session.delete(project)
            db.session.commit()
            return project.to_dict()
        return None

    def get_refactorings_for_project(self, id):
        project = Project.query.get(id)
        if project:
            return project.refactorings  # Assuming refactorings is a serializable object
        return []

    def detect_and_store_refactorings(self, id, refactorings):
        project = Project.query.get(id)
        if project:
            return project.to_dict()
        return None

        return None

    def get_projects(self):
        projects = Project.query.all()
        return [project.to_dict() for project in projects]

    def get_project_by_repo_path(self, repo_path):
        project = Project.query.filter_by(repo_path=repo_path).first()
        return project.to_dict() if project else None

def get_project_data(project_id):
    # Retrieve the project data from your database
    project = get_project_from_db(project_id)
    
    # Count the refactorings for each refactoring type
    refactoring_counts = {}
    for refactoring in project['refactorings']:
        refactoring_type = refactoring['type']
        if refactoring_type in refactoring_counts:
            refactoring_counts[refactoring_type] += 1
        else:
            refactoring_counts[refactoring_type] = 1

    # Return the refactoring counts and other project data
    return {
        'refactorings': refactoring_counts
    }
