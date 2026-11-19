"""Storage. Uses MongoDB if it is running; otherwise a JSON file (so you are never blocked)."""
import json, os

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "store.json")


class FileStore:
    kind = "JSON file"

    def __init__(self, path=DATA_FILE):
        self.path = path
        self.data = {}
        if os.path.exists(path):
            with open(path) as f:
                self.data = json.load(f)

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f)
        os.replace(tmp, self.path)

    def insert(self, coll, doc):
        self.data.setdefault(coll, []).append(dict(doc)); self._save()

    def all(self, coll):
        return [dict(d) for d in self.data.get(coll, [])]

    def replace(self, coll, docs):
        self.data[coll] = [dict(d) for d in docs]; self._save()


class MongoStore:
    kind = "MongoDB"

    def __init__(self, url="mongodb://localhost:27017", name="restaurant_ai"):
        from pymongo import MongoClient            # imported here so the project runs without it
        self.client = MongoClient(url, serverSelectionTimeoutMS=1500)
        self.client.admin.command("ping")           # raises if MongoDB is not running
        self.db = self.client[name]

    def insert(self, coll, doc):
        self.db[coll].insert_one(dict(doc))

    def all(self, coll):
        return list(self.db[coll].find({}, {"_id": 0}))

    def replace(self, coll, docs):
        self.db[coll].delete_many({})
        if docs:
            self.db[coll].insert_many([dict(d) for d in docs])


def make_store():
    try:
        s = MongoStore(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        print("[store] using MongoDB")
        return s
    except Exception as e:
        print("[store] MongoDB not available (%s). Using JSON file store." % type(e).__name__)
        return FileStore()
