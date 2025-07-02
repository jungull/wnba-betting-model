import json
import os

class ProgressTracker:
    def __init__(self, filepath='progress.json'):
        self.filepath = filepath
        self.progress = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                return json.load(f)
        return {}

    def save(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.progress, f)

    def update(self, key, value):
        self.progress[key] = value
        self.save()

    def get(self, key, default=None):
        return self.progress.get(key, default) 