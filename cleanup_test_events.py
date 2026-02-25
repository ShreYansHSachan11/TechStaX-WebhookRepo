#!/usr/bin/env python3
"""
Script to remove test events from MongoDB.
This will delete all events where the author is "testuser".
"""

from pymongo import MongoClient
import certifi
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get MongoDB connection details
MONGODB_URI = os.getenv('MONGODB_URI')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'TechStax')

def cleanup_test_events():
    """Remove all test events from the database."""
    try:
        print("Connecting to MongoDB...")
        
        # Connect to MongoDB
        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where(),
            tlsAllowInvalidCertificates=True
        )
        
        # Test connection
        client.admin.command('ping')
        print("✅ Connected to MongoDB successfully")
        
        # Get database and collection
        db = client[MONGODB_DATABASE]
        collection = db['webhook_events']
        
        # Count test events before deletion
        test_events_count = collection.count_documents({"author": "testuser"})
        print(f"\nFound {test_events_count} test events (author: testuser)")
        
        if test_events_count == 0:
            print("No test events to delete.")
            return
        
        # Ask for confirmation
        response = input(f"\nDo you want to delete these {test_events_count} test events? (yes/no): ")
        
        if response.lower() not in ['yes', 'y']:
            print("Deletion cancelled.")
            return
        
        # Delete test events
        result = collection.delete_many({"author": "testuser"})
        print(f"\n✅ Successfully deleted {result.deleted_count} test events")
        
        # Show remaining events count
        remaining_count = collection.count_documents({})
        print(f"📊 Remaining events in database: {remaining_count}")
        
        # Close connection
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧹 MongoDB Test Events Cleanup Script")
    print("=" * 50)
    cleanup_test_events()
