import chromadb

client = chromadb.PersistentClient(path='./data/chroma')

# Check all collections
collections = client.list_collections()
print('All collections:')
for col in collections:
    print(f'  {col.name}')

# Check the White Tiger collection specifically
try:
    col = client.get_collection('business__white_tiger_martial_arts')
    count = col.count()
    print(f'\nWhite Tiger collection has {count} documents')

    if count > 0:
        # Test a simple query
        results = col.query(query_texts=['programs'], n_results=2, include=['documents'])
        docs_found = len(results['documents'][0]) if results['documents'] else 0
        print(f'Simple query returned {docs_found} documents')

except Exception as e:
    print(f'Error accessing collection: {e}')