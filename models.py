from db import db

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repo_path = db.Column(db.String(500), nullable=False)
    commit_hash = db.Column(db.String(120), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'repo_path': self.repo_path,
            'commit_hash': self.commit_hash
        }

    def __repr__(self):
        return '<Project %r>' % self.repo_path
