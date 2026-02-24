import chromadb

client = chromadb.PersistentClient(path='./data/chroma')
col = client.get_collection('business__white_tiger_martial_arts')

# Get all documents
results = col.get(include=['documents'])
print('Current chunks in White Tiger collection:')
print(f'Total chunks: {len(results["documents"])}')
print()

for i, doc in enumerate(results['documents'][:3]):  # Show first 3 chunks
    print(f'Chunk {i+1} (length: {len(doc)} chars):')
    preview = doc[:200] + ('...' if len(doc) > 200 else '')
    print(repr(preview))
    print()