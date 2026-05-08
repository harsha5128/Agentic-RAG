// MongoDB Initialization Script
db = db.getSiblingDB('rag_db');

// Create collections
db.createCollection('documents');
db.createCollection('workflows');
db.createCollection('evaluations');
db.createCollection('cache');

// Create indexes
db.documents.createIndex({ document_id: 1 }, { unique: true });
db.documents.createIndex({ status: 1 });
db.documents.createIndex({ created_at: 1 });

db.workflows.createIndex({ workflow_id: 1 }, { unique: true });
db.workflows.createIndex({ created_at: 1 });

db.evaluations.createIndex({ query_id: 1 });
db.evaluations.createIndex({ created_at: 1 });

// Create indexes for document versioning
db.documents.createIndex({ document_id: 1, version: 1 }, { unique: true });

print("MongoDB initialization completed");
